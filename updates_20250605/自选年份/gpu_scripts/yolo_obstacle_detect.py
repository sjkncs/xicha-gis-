#!/usr/bin/env python3
"""
双视角障碍物检测 - 普通街景 + 低机位地面仰视
使用: yolo11x.pt (COCO基线) + yolov8x-world.pt (World模型)

检测视角划分：
  street_view  (普通街景视角)  → 图像中心偏上，无明显地面信息
  ground_view (低机位仰视)    → 图像下半部有台阶/坡道特征

障碍物类别映射 + 权重
"""

import os, json, time, sys, warnings
import numpy as np
import cv2
import torch

warnings.filterwarnings("ignore")
os.environ["YOLO_VERBOSE"] = "False"

# ========== 配置 ==========
REMOTE_DIR   = "/root/autodl-tmp/streetview_analysis"
IMG_DIR      = f"{REMOTE_DIR}/images"
OUT_DIR      = f"{REMOTE_DIR}/yolo_obstacle_results"
MODEL_DIR    = f"{REMOTE_DIR}/yolo_models"
DEVICE       = "cuda" if torch.cuda.is_available() else "cpu"
CONF_THRESH  = 0.35
IOU_THRESH   = 0.45
BATCH_SIZE   = 4

# ===== COCO → 中文映射 + 障碍权重 =====
COCO_CLASSES = {
    0: ("person", "人", 1.5),
    1: ("bicycle", "自行车", 1.5),
    2: ("car", "汽车", 2.0),
    3: ("motorcycle", "摩托车", 1.5),
    5: ("bus", "公交车", 2.0),
    7: ("truck", "货车", 2.0),
    9: ("traffic light", "红绿灯", 0.5),
    11: ("stop sign", "停车标志", 0.5),
    13: ("bench", "长椅", 1.5),
    14: ("backpack", "背包", 0.5),
    15: ("umbrella", "雨伞", 0.3),
    24: ("backpack", "背包", 0.5),
}

# ===== World模型类别（yolov8x-world支持的类）=====
WORLD_CLASSES = {
    0: ("person", "人", 1.5),
    1: ("bicycle", "自行车", 1.5),
    2: ("car", "汽车", 2.0),
    3: ("motorcycle", "摩托车", 1.5),
    4: ("airplane", "飞机", 0.1),
    5: ("bus", "公交车", 2.0),
    6: ("train", "火车", 0.5),
    7: ("truck", "货车", 2.0),
    8: ("boat", "船", 0.1),
    9: ("traffic light", "红绿灯", 0.5),
    10: ("fire hydrant", "消防栓", 0.5),
    11: ("stop sign", "停车标志", 0.5),
    12: ("parking meter", "停车计时器", 0.3),
    13: ("bench", "长椅", 1.5),
    14: ("bird", "鸟", 0.1),
    15: ("cat", "猫", 0.1),
    16: ("dog", "狗", 0.1),
    17: ("horse", "马", 0.1),
    18: ("sheep", "羊", 0.1),
    19: ("cow", "牛", 0.1),
    20: ("elephant", "大象", 0.1),
    21: ("bear", "熊", 0.1),
    22: ("zebra", "斑马", 0.1),
    23: ("giraffe", "长颈鹿", 0.1),
}

# ===== 手动指定要检测的World类 (yolov8x-world可自定义) =====
WORLD_OBSTACLE_CLASSES = {
    "bench":       ("bench",       "长椅",     1.5),
    "traffic cone":("cone",       "雪糕筒",   1.0),
    "trash can":   ("trash can",  "垃圾桶",   1.0),
    "fence":       ("fence",      "围栏",     1.5),
    "pole":        ("pole",       "杆柱",     0.8),
    "lamp":        ("lamp",       "路灯",     0.5),
    "stairs":      ("stairs",     "台阶楼梯",  2.5),
    "ramp":        ("ramp",       "坡道",     1.5),
    "curb":        ("curb",       "路缘石",   1.5),
    "bollard":     ("bollard",    "石墩",     1.5),
    "barrier":     ("barrier",    "路障",     2.0),
    "stroller":    ("stroller",   "婴儿车",   1.0),
    "wheelchair":   ("wheelchair", "轮椅",    1.5),
}

# ===== 区域权重（图像高度分区）=====
AREA_WEIGHTS = {
    "bottom": 0.5,   # 脚边权重最高（障碍最直接）
    "middle": 0.35,
    "top": 0.15,
}


def classify_view(img_path: str) -> str:
    """
    根据图片文件名特征判断视角
    - N/S/E/W 方位角 + "_N" 等表示相机朝向
    - U (up) 表示仰视
    - 路径含 step/stairs/ramp 等关键词
    """
    fname = os.path.basename(img_path).lower()
    dir_lower = img_path.lower()

    # 明确含仰视关键词 → ground_view
    if any(kw in dir_lower for kw in ["step", "stairs", "stair", "ramp", "坡", "台阶", "盲道"]):
        return "ground_view"

    # U方向 = Upward，仰视 → ground_view
    if "_U_" in fname or fname.endswith("_U.jpg") or "_U_" in dir_lower:
        return "ground_view"

    # 默认街景视角
    return "street_view"


def get_zone(y1: float, h: int) -> str:
    """判断 bbox 在图像高度方向的位置"""
    y_center_ratio = (y1 + 0.5) / h
    if y_center_ratio > 0.65: return "bottom"
    if y_center_ratio > 0.35: return "middle"
    return "top"


def load_models():
    """加载两个YOLO模型"""
    from ultralytics import YOLO

    print(f"Loading yolo11x.pt on {DEVICE}...")
    m1 = YOLO(f"{MODEL_DIR}/yolo11x.pt")
    m1.to(DEVICE)

    print(f"Loading yolov8x-world.pt on {DEVICE}...")
    m2 = YOLO(f"{MODEL_DIR}/yolov8x-world.pt")

    # 设置World模型类别（仅检测障碍相关类）
    world_labels = [
        "person", "bicycle", "car", "motorcycle", "bench", "stairs",
        "ramp", "curb", "bollard", "barrier", "trash can", "fence",
        "pole", "lamp", "traffic cone", "stroller", "wheelchair",
        "bicycle", "motorcycle"
    ]
    m2.set_classes(world_labels)
    m2.to(DEVICE)

    return m1, m2


def process_image(img_path: str, m1, m2) -> dict:
    """对单张图跑两个模型，合并结果"""
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        return None
    h, w = img_bgr.shape[:2]
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    view_type = classify_view(img_path)

    # --- Model 1: yolo11x (COCO) ---
    r1 = m1.predict(img_path, conf=CONF_THRESH, iou=IOU_THRESH,
                    verbose=False, device=DEVICE)

    # --- Model 2: yolov8x-world (自定义障碍类) ---
    r2 = m2.predict(img_path, conf=CONF_THRESH, iou=IOU_THRESH,
                    verbose=False, device=DEVICE)

    all_detections = []
    seen = {}  # (cx,cy,cls) -> True 做NMS-like去重

    # 解析 COCO 模型结果
    if len(r1) > 0 and r1[0].boxes is not None:
        boxes1 = r1[0].boxes
        for i in range(len(boxes1)):
            cls_id  = int(boxes1.cls[i].item())
            conf    = float(boxes1.conf[i].item())
            x1, y1, x2, y2 = boxes1.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = max(0,x1), max(0,y1), min(w,x2), min(h,y2)

            if cls_id not in COCO_CLASSES:
                continue
            cls_name, cls_cn, weight = COCO_CLASSES[cls_id]
            zone = get_zone(y1, h)
            composite = conf * weight * AREA_WEIGHTS[zone]

            # 过滤低质量检测（过小/过大bbox）
            bw, bh = x2-x1, y2-y1
            if bw < 10 or bh < 10 or bw > w*0.95 or bh > h*0.95:
                continue

            key = (int((x1+x2)/2/w*10), int((y1+y2)/2/h*10), cls_name)
            if key in seen and seen[key] >= composite:
                continue
            seen[key] = composite

            all_detections.append({
                "model": "coco",
                "class": cls_name,
                "class_cn": cls_cn,
                "conf": round(conf, 3),
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "weight": weight,
                "zone": zone,
                "composite": round(composite, 4),
                "category": cls_cn,
            })

    # 解析 World 模型结果
    if len(r2) > 0 and r2[0].boxes is not None:
        boxes2 = r2[0].boxes
        for i in range(len(boxes2)):
            cls_name = str(boxes2.cls[i].item())
            conf     = float(boxes2.conf[i].item())
            x1, y1, x2, y2 = boxes2.xyxy[i].cpu().numpy()
            x1, y1, x2, y2 = max(0,x1), max(0,y1), min(w,x2), min(h,y2)

            cls_name_clean = cls_name.strip()
            if cls_name_clean not in WORLD_OBSTACLE_CLASSES:
                continue
            _, cls_cn, weight = WORLD_OBSTACLE_CLASSES[cls_name_clean]
            zone = get_zone(y1, h)
            composite = conf * weight * AREA_WEIGHTS[zone]

            bw, bh = x2-x1, y2-y1
            if bw < 10 or bh < 10 or bw > w*0.95 or bh > h*0.95:
                continue

            key = (int((x1+x2)/2/w*10), int((y1+y2)/2/h*10), cls_name_clean)
            if key in seen and seen[key] >= composite:
                continue
            seen[key] = composite

            all_detections.append({
                "model": "world",
                "class": cls_name_clean,
                "class_cn": cls_cn,
                "conf": round(conf, 3),
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "weight": weight,
                "zone": zone,
                "composite": round(composite, 4),
                "category": cls_cn,
            })

    # 计算综合可达性分数（越高=越不通畅）
    total_score = sum(d["composite"] for d in all_detections)
    accessibility_score = min(100.0, total_score * 10)

    # 分类统计
    cat_count = {}
    for d in all_detections:
        cat = d["category"]
        cat_count[cat] = cat_count.get(cat, 0) + 1

    return {
        "image": img_path,
        "view_type": view_type,
        "detections": all_detections,
        "total_obstacles": len(all_detections),
        "accessibility_score": round(accessibility_score, 2),
        "categories": cat_count,
    }


def draw_vis(img_path: str, result: dict, out_path: str):
    """绘制检测可视化"""
    img = cv2.imread(img_path)
    if img is None:
        return
    h, w = img.shape[:2]

    cat_colors = {
        "人":         (80, 160, 255),
        "汽车":       (80, 100, 255),
        "自行车":     (100, 200, 255),
        "摩托车":     (120, 180, 255),
        "公交车":     (60, 80, 200),
        "货车":       (60, 80, 200),
        "红绿灯":     (0, 200, 200),
        "停车标志":   (0, 180, 180),
        "长椅":       (200, 100, 150),
        "台阶楼梯":   (255, 80, 80),
        "坡道":       (255, 160, 80),
        "路缘石":     (200, 200, 80),
        "石墩":       (150, 100, 200),
        "路障":       (255, 80, 150),
        "雪糕筒":     (255, 140, 0),
        "垃圾桶":     (140, 140, 140),
        "围栏":       (100, 180, 100),
        "杆柱":       (120, 120, 120),
        "轮椅":       (0, 200, 100),
        "婴儿车":     (200, 150, 100),
    }

    for det in result["detections"]:
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        color = cat_colors.get(det["category_cn"], (200, 200, 200))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = "%s %.2f" % (det["category_cn"], det["conf"])
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        cv2.rectangle(img, (x1, y1-th-3), (x1+tw+4, y1), color, -1)
        cv2.putText(img, label, (x1+2, y1-2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 1)

    # 左上角视角标签
    view_color = (100, 255, 100) if result["view_type"] == "street_view" else (255, 200, 80)
    cv2.putText(img, result["view_type"], (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, view_color, 2)

    # 右下角综合评分
    score = result["accessibility_score"]
    score_color = (0, 255, 0) if score < 30 else (0, 255, 255) if score < 60 else (0, 80, 255)
    cv2.putText(img, "Score:%.1f  Obs:%d" % (score, result["total_obstacles"]),
                (8, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, score_color, 2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, img, [cv2.IMWRITE_JPEG_QUALITY, 90])


def generate_heatmap(all_results: list, out_dir: str):
    """按视角分组建分类热图"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm

    # 找字体
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/root/.cache/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf",
    ]
    font_path = next((f for f in font_paths if os.path.exists(f)), None)
    plt.rcParams["font.family"] = "DejaVu Sans"
    if font_path:
        fm.fontManager.addfont(font_path)
        plt.rcParams["font.sans-serif"] = [os.path.basename(font_path).replace(".ttf","")]

    for view_type in ["street_view", "ground_view"]:
        view_results = [r for r in all_results if r["view_type"] == view_type]
        if not view_results:
            continue

        # 统计各障碍类别数量
        cat_total = {}
        for r in view_results:
            for cat, cnt in r["categories"].items():
                cat_total[cat] = cat_total.get(cat, 0) + cnt

        if not cat_total:
            continue

        # 排序
        sorted_cats = sorted(cat_total.items(), key=lambda x: -x[1])
        cats = [c[0] for c in sorted_cats]
        vals = [c[1] for c in sorted_cats]

        fig, ax = plt.subplots(figsize=(10, max(4, len(cats) * 0.4 + 2)))
        colors = plt.cm.Reds(np.linspace(0.3, 0.9, len(cats)))
        ax.barh(range(len(cats)), vals, color=colors)
        ax.set_yticks(range(len(cats)))
        ax.set_yticklabels(cats, fontsize=10)
        ax.set_xlabel("Count", fontsize=10)
        ax.set_title("Obstacle Categories (%s) - %d images" % (view_type, len(view_results)),
                     fontsize=12, fontweight="bold")
        for i, v in enumerate(vals):
            ax.text(v + 0.5, i, str(v), va="center", fontsize=9)
        plt.tight_layout()
        os.makedirs(out_dir, exist_ok=True)
        plt.savefig(f"{out_dir}/category_bar_{view_type}.png", dpi=150, bbox_inches="tight")
        plt.close()

        print("  Saved: category_bar_%s.png" % view_type)

        # 评分分布
        scores = [r["accessibility_score"] for r in view_results]
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        ax2.hist(scores, bins=20, color="steelblue", edgecolor="white", alpha=0.8)
        ax2.axvline(np.mean(scores), color="red", linestyle="--", label="Mean: %.1f" % np.mean(scores))
        ax2.set_xlabel("Accessibility Score (higher=more obstacles)", fontsize=10)
        ax2.set_ylabel("Number of Images", fontsize=10)
        ax2.set_title("Score Distribution (%s)" % view_type, fontsize=12)
        ax2.legend()
        plt.tight_layout()
        plt.savefig(f"{out_dir}/score_dist_{view_type}.png", dpi=150, bbox_inches="tight")
        plt.close()
        print("  Saved: score_dist_%s.png" % view_type)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{OUT_DIR}/viz", exist_ok=True)

    print(f"Device: {DEVICE}")
    print(f"Loading models...")
    m1, m2 = load_models()
    print("Models loaded.")

    # 收集所有图片
    exts = [".jpg", ".jpeg", ".png", ".JPG"]
    image_files = []
    skip_names = {"building_coverage", "scatter", "histogram", "radar",
                  "urban_form", "obstacle", "heatmap", "category_bar", "score_dist"}
    for root, dirs, files in os.walk(IMG_DIR):
        for f in files:
            if any(f.endswith(e) for e in exts):
                if any(sn in f for sn in skip_names):
                    continue
                image_files.append(os.path.join(root, f))

    image_files = sorted(image_files)
    print(f"Found {len(image_files)} images")

    all_results = []
    for i, img_path in enumerate(image_files):
        fname = os.path.basename(img_path).rsplit(".", 1)[0]
        viz_path = f"{OUT_DIR}/viz/{fname}_det.jpg"

        try:
            result = process_image(img_path, m1, m2)
            if result is None:
                continue
            all_results.append(result)
            draw_vis(img_path, result, viz_path)
        except Exception as e:
            print("ERROR [%d/%d] %s: %s" % (i+1, len(image_files), fname, e))
            import traceback
            traceback.print_exc()
            continue

        if (i + 1) % 20 == 0 or i == len(image_files) - 1:
            print("  Processed %d/%d" % (i+1, len(image_files)))

    # 汇总统计
    print("\nGenerating summary...")
    generate_heatmap(all_results, OUT_DIR)

    # 街道级统计
    street_stats = {}
    for r in all_results:
        # 从路径提取街道名
        parts = r["image"].split(os.sep)
        # e.g. .../街道/社区/OpenOther/经纬度/文件.jpg
        if len(parts) >= 4:
            street = parts[-4]
        else:
            street = "unknown"

        if street not in street_stats:
            street_stats[street] = {
                "count": 0, "scores": [], "total_obs": 0,
                "view_types": {"street_view": 0, "ground_view": 0},
                "categories": {}
            }
        street_stats[street]["count"] += 1
        street_stats[street]["scores"].append(r["accessibility_score"])
        street_stats[street]["total_obs"] += r["total_obstacles"]
        street_stats[street]["view_types"][r["view_type"]] += 1
        for cat, cnt in r["categories"].items():
            street_stats[street]["categories"][cat] = \
                street_stats[street]["categories"].get(cat, 0) + cnt

    for street, data in street_stats.items():
        scores = data["scores"]
        data["mean_score"] = round(sum(scores)/len(scores), 2) if scores else 0
        data["max_score"]  = round(max(scores), 2) if scores else 0
        data["min_score"]  = round(min(scores), 2) if scores else 0
        del data["scores"]

    # 全局障碍类型统计
    global_cats = {}
    for r in all_results:
        for cat, cnt in r["categories"].items():
            global_cats[cat] = global_cats.get(cat, 0) + cnt

    # 保存JSON
    with open(f"{OUT_DIR}/all_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/street_stats.json", "w", encoding="utf-8") as f:
        json.dump(street_stats, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/global_categories.json", "w", encoding="utf-8") as f:
        json.dump(global_cats, f, ensure_ascii=False, indent=2)

    # 打印摘要
    print("\n" + "="*60)
    print("RESULT SUMMARY")
    print("="*60)
    print(f"Total images: {len(all_results)}")
    street_view_n = sum(1 for r in all_results if r["view_type"]=="street_view")
    ground_view_n = sum(1 for r in all_results if r["view_type"]=="ground_view")
    print(f"  street_view: {street_view_n}")
    print(f"  ground_view: {ground_view_n}")
    print(f"\nGlobal obstacle counts:")
    for cat, cnt in sorted(global_cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")
    print(f"\nStreet accessibility (mean score):")
    for street, data in sorted(street_stats.items(), key=lambda x: -x[1]["mean_score"]):
        print(f"  {street}: score={data['mean_score']} obs={data['total_obs']} imgs={data['count']}")
    print(f"\nOutput: {OUT_DIR}/")
    print(f"  all_results.json")
    print(f"  street_stats.json")
    print(f"  global_categories.json")
    print(f"  viz/*.jpg (per-image visualizations)")
    print(f"  category_bar_street_view.png")
    print(f"  category_bar_ground_view.png")
    print(f"  score_dist_street_view.png")
    print(f"  score_dist_ground_view.png")


if __name__ == "__main__":
    main()
