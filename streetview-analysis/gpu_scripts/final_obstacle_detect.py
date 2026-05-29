#!/usr/bin/env python3
"""
障碍物检测 - 最终版
只依赖 yolo11x.pt (COCO基线，最稳定)
双视角分类: street_view / ground_view
"""

import os, sys, json, time, warnings
os.environ["YOLO_VERBOSE"] = "False"
warnings.filterwarnings("ignore")

import numpy as np
import cv2
import torch
from ultralytics import YOLO

# ========== 配置 ==========
REMOTE_DIR  = "/root/autodl-tmp/streetview_analysis"
IMG_DIR     = f"{REMOTE_DIR}/images"
OUT_DIR     = f"{REMOTE_DIR}/yolo_obstacle_results"
MODEL_DIR   = f"{REMOTE_DIR}/yolo_models"
MODEL_PATH  = f"{MODEL_DIR}/yolo11x.pt"
DEVICE      = "cuda" if torch.cuda.is_available() else "cpu"
CONF_THRESH = 0.35
IOU_THRESH  = 0.45

# ========== COCO类 → 障碍物映射 ==========
# 格式: coco_id -> (coco_name, cn_label, accessibility_weight)
COCO_OBSTACLE_MAP = {
    0:  ("person",          "行人/使用者",       1.5),  # 行人（有遮挡作用）
    1:  ("bicycle",        "自行车占道",        1.5),
    2:  ("car",            "汽车占道",          2.0),
    3:  ("motorcycle",     "摩托车/电动车",      1.5),
    5:  ("bus",            "公交车占道",        2.0),
    7:  ("truck",          "货车占道",          2.0),
    11: ("stop sign",      "停车让行标志",       0.3),
    13: ("bench",          "长椅占道",          1.5),
    14: ("backpack",       "背包(小障碍)",      0.3),
    24: ("backpack",       "背包",              0.3),
    31: ("tie",            "领带",              0.1),  # 极低优先级
}

# 视角分类关键词
GROUND_VIEW_KEYWORDS = [
    "step", "stairs", "stair", "ramp", "盲道",
    "step", "ramp", "台阶", "楼梯", "盲道",
]

STREET_VIEW_KEYWORDS = [
    "barrier", "cone", "bollard", "石墩", "路障",
    "traffic", "sign", "交通", "灯", "light",
    "car", "truck", "bus", "parked", "占道",
    "construction", "施工", "围挡",
]

# 区域权重
AREA_WEIGHTS = {"bottom": 0.50, "middle": 0.35, "top": 0.15}


def classify_view(img_path: str) -> str:
    """根据路径/文件名判断视角"""
    p = img_path.lower()
    # ground_view: 含台阶/坡道/楼梯关键词
    for kw in GROUND_VIEW_KEYWORDS:
        if kw.lower() in p:
            return "ground_view"
    # U方向 (Upward) = 仰视
    fname = os.path.basename(img_path)
    if "_U_" in fname or fname.endswith("_U.jpg") or "_U_" in p:
        return "ground_view"
    return "street_view"


def get_zone(y1_norm: float) -> str:
    """根据归一化y1判断高度区域（bottom=脚边，top=远处）"""
    if y1_norm > 0.65: return "bottom"
    if y1_norm > 0.35: return "middle"
    return "top"


def load_model():
    """加载YOLO11x模型"""
    print(f"Loading yolo11x on {DEVICE}...", flush=True)
    model = YOLO(MODEL_PATH)
    model.to(DEVICE)
    # 预热一次
    dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
    model.predict(dummy_img, verbose=False)
    print("Model ready.", flush=True)
    return model


def process_image(img_path: str, model) -> dict:
    """检测单张图片"""
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        return None
    h, w = img_bgr.shape[:2]

    view_type = classify_view(img_path)

    results = model.predict(
        img_path,
        conf=CONF_THRESH,
        iou=IOU_THRESH,
        verbose=False,
        device=DEVICE,
    )

    detections = []
    if results and results[0].boxes is not None:
        boxes = results[0].boxes
        for i in range(len(boxes)):
            cls_id = int(boxes.cls[i].item())
            if cls_id not in COCO_OBSTACLE_MAP:
                continue

            conf = float(boxes.conf[i].item())
            x1, y1, x2, y2 = boxes.xyxy[i].cpu().numpy()
            # 归一化
            x1n, y1n = x1 / w, y1 / h
            x2n, y2n = x2 / w, y2 / h

            coco_name, cn_label, weight = COCO_OBSTACLE_MAP[cls_id]
            zone = get_zone(y1n)
            composite = conf * weight * AREA_WEIGHTS[zone]

            # 过滤极小/极大bbox
            bw, bh = x2 - x1, y2 - y1
            if bw < 8 or bh < 8 or bw > w * 0.95 or bh > h * 0.95:
                continue

            detections.append({
                "coco_id": cls_id,
                "coco_name": coco_name,
                "cn_label": cn_label,
                "conf": round(conf, 3),
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "bbox_norm": [round(x1n,4), round(y1n,4), round(x2n,4), round(y2n,4)],
                "zone": zone,
                "weight": weight,
                "composite": round(composite, 4),
            })

    # 统计
    cat_count = {}
    for d in detections:
        cat = d["cn_label"]
        cat_count[cat] = cat_count.get(cat, 0) + 1

    # 可达性分数（越高=障碍越多，越不通畅）
    score = min(100.0, sum(d["composite"] for d in detections) * 10)

    return {
        "image": img_path,
        "view_type": view_type,
        "detections": detections,
        "total_obstacles": len(detections),
        "accessibility_score": round(score, 2),
        "categories": cat_count,
    }


def draw_detection(img_path: str, result: dict, out_path: str):
    """绘制检测结果"""
    img = cv2.imread(img_path)
    if img is None:
        return
    h, w = img.shape[:2]

    colors = {
        "行人/使用者": (80, 160, 255),
        "汽车占道":   (80, 80, 255),
        "自行车占道": (100, 200, 255),
        "摩托车/电动车": (120, 180, 255),
        "公交车占道": (60, 80, 200),
        "货车占道":   (60, 80, 200),
        "长椅占道":   (200, 100, 150),
        "停车让行标志": (0, 200, 200),
    }

    for det in result["detections"]:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        color = colors.get(det["cn_label"], (200, 200, 200))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = "%s %.2f" % (det["cn_label"], det["conf"])
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(img, (x1, y1-th-3), (x1+tw+4, y1), color, -1)
        cv2.putText(img, label, (x1+2, y1-2),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)

    # 左上：视角标签
    vt = result["view_type"]
    vt_color = (100, 255, 100) if vt == "street_view" else (255, 200, 80)
    cv2.putText(img, vt, (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, vt_color, 2)

    # 右下：综合评分
    sc = result["accessibility_score"]
    sc_color = (0, 255, 0) if sc < 30 else (0, 255, 255) if sc < 60 else (0, 80, 255)
    cv2.putText(img, "Score:%.1f  Obs:%d" % (sc, result["total_obstacles"]),
                (8, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, sc_color, 2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, 85])


def generate_charts(all_results: list, out_dir: str):
    """生成分类条形图和评分分布图"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm

        # 找中文字体
        font_dirs = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
            "/root/.cache/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        font_path = next((f for f in font_dirs if os.path.exists(f)), None)
        if font_path:
            fm.fontManager.addfont(font_path)
            fname = os.path.splitext(os.path.basename(font_path))[0]
            plt.rcParams["font.family"] = fname

        plt.rcParams["axes.unicode_minus"] = False
    except Exception as e:
        print("  matplotlib font setup failed:", e, flush=True)
        font_path = None

    for view_type in ["street_view", "ground_view"]:
        view_results = [r for r in all_results if r["view_type"] == view_type]
        if not view_results:
            continue

        cat_total = {}
        for r in view_results:
            for cat, cnt in r["categories"].items():
                cat_total[cat] = cat_total.get(cat, 0) + cnt

        if not cat_total:
            continue

        sorted_items = sorted(cat_total.items(), key=lambda x: -x[1])

        # 条形图
        fig, ax = plt.subplots(figsize=(10, max(4, len(sorted_items) * 0.4 + 1.5)))
        cats = [c[0] for c in sorted_items]
        vals = [c[1] for c in sorted_items]
        colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(cats)))
        ax.barh(range(len(cats)), vals, color=colors)
        ax.set_yticks(range(len(cats)))
        ax.set_yticklabels(cats, fontsize=10)
        ax.set_xlabel("Count", fontsize=10)
        title = f"Obstacle Category Counts ({view_type}) - {len(view_results)} images"
        ax.set_title(title, fontsize=11, fontweight="bold")
        for i, v in enumerate(vals):
            ax.text(v + 0.3, i, str(v), va="center", fontsize=9)
        ax.set_xlim(0, max(vals) * 1.15)
        plt.tight_layout()
        os.makedirs(out_dir, exist_ok=True)
        plt.savefig(f"{out_dir}/category_bar_{view_type}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved category_bar_{view_type}.png", flush=True)

        # 评分分布
        scores = [r["accessibility_score"] for r in view_results]
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        ax2.hist(scores, bins=15, color="steelblue", edgecolor="white", alpha=0.85)
        mean_s = np.mean(scores)
        ax2.axvline(mean_s, color="red", linestyle="--", linewidth=1.5,
                    label="Mean: %.1f" % mean_s)
        ax2.set_xlabel("Accessibility Score (higher=more obstacles)", fontsize=10)
        ax2.set_ylabel("Number of Images", fontsize=10)
        ax2.set_title(f"Score Distribution ({view_type})", fontsize=11)
        ax2.legend()
        plt.tight_layout()
        plt.savefig(f"{out_dir}/score_dist_{view_type}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  Saved score_dist_{view_type}.png", flush=True)


def main():
    t_start = time.time()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{OUT_DIR}/viz", exist_ok=True)

    print(f"Device: {DEVICE}", flush=True)
    print(f"Model: {MODEL_PATH}", flush=True)

    model = load_model()

    # 收集所有图片
    skip_names = {"building_coverage", "scatter", "histogram", "radar",
                  "urban_form", "obstacle", "heatmap", "category_bar",
                  "score_dist", "fcn", "segmentation"}
    exts = {".jpg", ".jpeg", ".png", ".JPG"}
    image_files = []
    for root, dirs, files in os.walk(IMG_DIR):
        for f in files:
            if any(f.endswith(e) for e in exts) and not any(s in f for s in skip_names):
                image_files.append(os.path.join(root, f))

    image_files = sorted(image_files)
    print(f"Found {len(image_files)} images", flush=True)

    all_results = []
    for i, img_path in enumerate(image_files):
        fname = os.path.basename(img_path).rsplit(".", 1)[0]
        viz_path = f"{OUT_DIR}/viz/{fname}_det.jpg"

        try:
            result = process_image(img_path, model)
            if result is None:
                continue
            all_results.append(result)
            draw_detection(img_path, result, viz_path)
        except Exception as e:
            print(f"ERROR [{i+1}/{len(image_files)}] {fname}: {e}", flush=True)
            import traceback; traceback.print_exc()

        if (i + 1) % 20 == 0 or i == len(image_files) - 1:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            eta = (len(image_files) - i - 1) / rate if rate > 0 else 0
            print(f"  Progress: {i+1}/{len(image_files)} | "
                  f"Elapsed: {elapsed:.0f}s | ETA: {eta:.0f}s", flush=True)

    # 生成图表
    print("Generating charts...", flush=True)
    generate_charts(all_results, OUT_DIR)

    # 街道级统计
    street_stats = {}
    for r in all_results:
        parts = r["image"].split(os.sep)
        street = parts[-4] if len(parts) >= 4 else "unknown"
        if street not in street_stats:
            street_stats[street] = {
                "count": 0, "scores": [], "total_obs": 0,
                "view_counts": {"street_view": 0, "ground_view": 0},
                "categories": {}
            }
        street_stats[street]["count"] += 1
        street_stats[street]["scores"].append(r["accessibility_score"])
        street_stats[street]["total_obs"] += r["total_obstacles"]
        street_stats[street]["view_counts"][r["view_type"]] += 1
        for cat, cnt in r["categories"].items():
            street_stats[street]["categories"][cat] = \
                street_stats[street]["categories"].get(cat, 0) + cnt

    for street, data in street_stats.items():
        scores = data["scores"]
        data["mean_score"] = round(sum(scores)/len(scores), 2) if scores else 0
        data["max_score"] = round(max(scores), 2) if scores else 0
        data["min_score"] = round(min(scores), 2) if scores else 0
        del data["scores"]

    # 全局障碍统计
    global_cats = {}
    for r in all_results:
        for cat, cnt in r["categories"].items():
            global_cats[cat] = global_cats.get(cat, 0) + cnt

    # 保存
    print("Saving JSON results...", flush=True)
    with open(f"{OUT_DIR}/all_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    with open(f"{OUT_DIR}/street_stats.json", "w", encoding="utf-8") as f:
        json.dump(street_stats, f, ensure_ascii=False, indent=2)
    with open(f"{OUT_DIR}/global_categories.json", "w", encoding="utf-8") as f:
        json.dump(global_cats, f, ensure_ascii=False, indent=2)

    # 打印摘要
    total_time = time.time() - t_start
    sv = sum(1 for r in all_results if r["view_type"]=="street_view")
    gv = sum(1 for r in all_results if r["view_type"]=="ground_view")

    print("\n" + "="*65, flush=True)
    print("RESULT SUMMARY", flush=True)
    print("="*65, flush=True)
    print(f"Total images: {len(all_results)}", flush=True)
    print(f"  street_view: {sv}  ground_view: {gv}", flush=True)
    print(f"Time: {total_time:.0f}s  ({total_time/len(all_results):.2f}s/img)", flush=True)

    print(f"\nGlobal obstacle counts:", flush=True)
    for cat, cnt in sorted(global_cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}", flush=True)

    print(f"\nStreet accessibility (score, higher=more obstacles):", flush=True)
    for street, data in sorted(street_stats.items(), key=lambda x: -x[1]["mean_score"]):
        print(f"  {street}: score={data['mean_score']} "
              f"obs={data['total_obs']} imgs={data['count']}", flush=True)

    print(f"\nOutput: {OUT_DIR}/", flush=True)
    print(f"  all_results.json  (per-image detections)", flush=True)
    print(f"  street_stats.json (per-street summary)", flush=True)
    print(f"  global_categories.json", flush=True)
    print(f"  viz/*.jpg         (detection visualizations)", flush=True)
    print(f"  category_bar_*.png", flush=True)
    print(f"  score_dist_*.png", flush=True)


if __name__ == "__main__":
    main()
