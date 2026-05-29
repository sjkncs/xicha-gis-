#!/usr/bin/env python3
"""
Grounding DINO 障碍物检测脚本 - 无障碍可达性分析
检测类别：
  - 台阶/楼梯 (stairs, step, staircase, stairway)
  - 轮椅坡道 (ramp, wheelchair ramp, sloped ramp)
  - 路障/施工围挡 (barrier, roadblock, construction barrier, jersey barrier)
  - 雪糕筒/锥桶 (traffic cone, safety cone, cone)
  - 减速带 (speed bump, speed hump, sleeping policeman, road hump)
  - 石墩/矮柱 (stone pillar, bollard, concrete block, post)
  - 路面破损 (pothole, cracked pavement, broken sidewalk, crack)
  - 路缘石 (curb, raised curb, curb ramp)
  - 占道车辆 (car on sidewalk, vehicle on path)
  - 低矮障碍 (bench blocking path, garbage bin, street furniture)
  - 围栏 (fence, railing, handrail)
"""

import os, json, time, warnings, textwrap
import numpy as np
import torch
import cv2
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")

# ========== 配置 ==========
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
OUT_DIR   = f"{REMOTE_DIR}/grounding_results"
IMG_DIR   = f"{REMOTE_DIR}/images"
BOX_TRESHOLD = 0.35
TEXT_TRESHOLD = 0.25
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# 障碍物文字描述（用 . 分隔类别，权重映射）
OBSTACLE_PROMPT = (
    "stairs. step. staircase. stairway. "
    "ramp. sloped ramp. wheelchair ramp. inclined surface. "
    "barrier. roadblock. construction barrier. jersey barrier. concrete barrier. "
    "traffic cone. safety cone. orange cone. "
    "speed bump. speed hump. road hump. sleeping policeman. "
    "bollard. stone pillar. concrete block. post. "
    "pothole. cracked pavement. broken sidewalk. crack. gap. "
    "curb. raised curb. curb edge. "
    "fence. railing. handrail. low wall. "
    "bench on sidewalk. street furniture blocking path. "
    "car on sidewalk. vehicle on path. "
    "construction fence. scaffolding blocking view. "
    "wire pole. utility pole. sign pole. "
    "trash bin blocking. parked bicycle on path."
)

# 类别 → 中文标签 + 权重
OBSTACLE_CATEGORIES = {
    "stairs/step/staircase/stairway": ("台阶/楼梯", 3.0),
    "ramp": ("轮椅坡道", 1.0),
    "barrier": ("路障/围挡", 2.5),
    "cone": ("锥桶", 1.0),
    "speed bump": ("减速带", 1.5),
    "bollard/pillar/post": ("石墩/立柱", 2.0),
    "pothole/crack": ("路面破损", 2.0),
    "curb": ("路缘石", 1.5),
    "fence/railing": ("围栏/扶手", 2.0),
    "bench/furniture": ("占道设施", 1.5),
    "car/vehicle": ("占道车辆", 2.5),
    "construction": ("施工围挡", 2.0),
    "pole": ("杆柱", 1.0),
}

# 区域权重（图像高度分为3层）
AREA_WEIGHTS = {
    "bottom": 0.5,   # 底部（脚边）权重最高
    "middle": 0.35,  # 中部
    "top": 0.15,    # 顶部（天空/远处）
}


def map_class_to_category(class_name: str) -> str:
    """将检测到的类别映射到障碍物大类"""
    c = class_name.lower()
    if any(w in c for w in ["stairs", "step", "staircase", "stairway"]): return "stairs/step/staircase/stairway"
    if "ramp" in c: return "ramp"
    if "barrier" in c: return "barrier"
    if "cone" in c: return "cone"
    if any(w in c for w in ["speed bump", "hump", "road hump"]): return "speed bump"
    if any(w in c for w in ["bollard", "pillar", "post", "block"]): return "bollard/pillar/post"
    if any(w in c for w in ["pothole", "crack", "broken", "gap"]): return "pothole/crack"
    if "curb" in c: return "curb"
    if any(w in c for w in ["fence", "railing", "handrail", "wall"]): return "fence/railing"
    if any(w in c for w in ["bench", "furniture", "bin"]): return "bench/furniture"
    if any(w in c for w in ["car", "vehicle", "bicycle"]): return "car/vehicle"
    if any(w in c for w in ["construction", "scaffold"]): return "construction"
    if "pole" in c: return "pole"
    return "other"


def get_area_zone(y1: float, h: int) -> str:
    """判断bbox在图像的哪个高度区域"""
    y_center_ratio = (y1 + 0.5 * h) / h
    if y_center_ratio > 0.65: return "bottom"
    if y_center_ratio > 0.35: return "middle"
    return "top"


def load_gdino():
    """加载 Grounding DINO 模型"""
    from groundingdino.models import build_model
    from groundingdino.util.slconfig import SLConfig
    import groundingdino.datasets.transforms as T

    model_cfg_path = os.path.join(REMOTE_DIR, "groundingdino/config.py")
    model_weight_path = os.path.join(REMOTE_DIR, "groundingdino/groundingdino_swint_ogc.pth")

    if not os.path.exists(model_cfg_path) or not os.path.exists(model_weight_path):
        raise FileNotFoundError(
            f"Grounding DINO 模型文件缺失:\n"
            f"  config: {model_cfg_path}\n"
            f"  weight: {model_weight_path}\n"
            f"请先运行 install_gdino.py 安装"
        )

    args = SLConfig.fromfile(model_cfg_path)
    model = build_model(args)
    checkpoint = torch.load(model_weight_path, map_location="cpu")
    model.load_state_dict(checkpoint, strict=False)
    model.eval()
    model.to(DEVICE)
    return model


def build_caption():
    """构建类别提示词"""
    return OBSTACLE_PROMPT


def detect_image(model, image_path: str, out_viz_path: str = None) -> dict:
    """对单张图运行 Grounding DINO 检测"""
    import groundingdino.datasets.transforms as T

    image = Image.open(image_path).convert("RGB")
    w, h = image.size

    transform = T.Compose([
        T.RandomResize([800], max_size=1333),
        T.ToTensor(),
        T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    image_tensor, _ = transform(image, None)

    caption = build_caption()
    with torch.no_grad():
        outputs = model([image_tensor.to(DEVICE)], captions=[caption])

    # 解析检测结果
    logits = outputs["pred_logits"].cpu()[0].sigmoid()
    boxes  = outputs["pred_boxes"].cpu()[0]

    # 过滤阈值
    score_filter = (logits.max(dim=1)[0] > BOX_TRESHOLD)
    scores = logits.max(dim=1)[0][score_filter]
    bboxes = boxes[score_filter]

    # 解析类别
    labels = []
    for i in range(len(scores)):
        idx = logits[i].argmax().item()
        labels.append(caption.split(".")[idx].strip() if idx < len(caption.split(".")) else "unknown")

    results = {
        "image": image_path,
        "detections": [],
        "total_obstacles": len(scores),
        "accessibility_score": 0.0,
        "categories": {},
        "zones": {"bottom": 0, "middle": 0, "top": 0},
    }

    if len(scores) == 0:
        return results

    # 转换 bbox (xyxy, 绝对像素)
    img_np = np.array(image)
    for box, score, label in zip(bboxes, scores, labels):
        x1, y1, x2, y2 = box.tolist()
        x1, x2 = int(x1 * w), int(x2 * w)
        y1, y2 = int(y1 * h), int(y2 * h)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        cat = map_class_to_category(label)
        cat_info = next((v for k, v in OBSTACLE_CATEGORIES.items() if cat in k), ("其他", 1.0))
        if isinstance(cat_info, tuple): _, weight = cat_info
        else: weight = cat_info[1]

        zone = get_area_zone(y1, h)
        zone_weight = AREA_WEIGHTS[zone]

        # 综合分数 = 置信度 * 类别权重 * 区域权重
        composite = float(score) * weight * zone_weight

        det = {
            "class": label,
            "category": cat,
            "category_cn": cat_info[0] if isinstance(cat_info, tuple) else cat_info[0],
            "score": float(score),
            "bbox": [x1, y1, x2, y2],
            "zone": zone,
            "weight": weight,
            "composite_score": composite,
        }
        results["detections"].append(det)

        # 统计
        if cat not in results["categories"]:
            results["categories"][cat] = {"count": 0, "total_score": 0.0}
        results["categories"][cat]["count"] += 1
        results["categories"][cat]["total_score"] += composite

        results["zones"][zone] += 1

    # 综合可达性分数（越高=越不通畅，0-100）
    total_score = sum(d["composite_score"] for d in results["detections"])
    results["accessibility_score"] = min(100.0, total_score * 10)

    # 可视化
    if out_viz_path:
        draw_vis(image_path, results, out_viz_path)

    return results


def draw_vis(image_path: str, result: dict, out_path: str):
    """绘制检测可视化结果"""
    img = cv2.imread(image_path)
    h, w = img.shape[:2]

    # 类别颜色映射
    cat_colors = {
        "stairs/step/staircase/stairway": (255, 80, 80),
        "ramp": (255, 180, 80),
        "barrier": (255, 100, 100),
        "cone": (255, 165, 0),
        "speed bump": (200, 150, 0),
        "bollard/pillar/post": (150, 100, 200),
        "pothole/crack": (180, 80, 80),
        "curb": (200, 200, 100),
        "fence/railing": (100, 180, 100),
        "bench/furniture": (180, 100, 180),
        "car/vehicle": (100, 150, 255),
        "construction": (255, 80, 150),
        "pole": (150, 150, 150),
        "other": (200, 200, 200),
    }

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(font_path):
        font_path = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    try:
        font = ImageFont.truetype(font_path, 14)
    except:
        font = ImageFont.load_default()

    for det in result["detections"]:
        x1, y1, x2, y2 = det["bbox"]
        color = cat_colors.get(det["category"], (200, 200, 200))
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        label = f"{det['category_cn']} {det['score']:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(img, (x1, y1-th-4), (x1+tw+4, y1), color, -1)
        cv2.putText(img, label, (x1+2, y1-2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)

    # 右下角综合评分
    score = result["accessibility_score"]
    score_label = f"Score: {score:.1f}"
    cv2.putText(img, score_label, (10, h-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)

    # 障碍物数量
    count_label = f"Obstacles: {result['total_obstacles']}"
    cv2.putText(img, count_label, (10, h-40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, img)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(f"{OUT_DIR}/viz", exist_ok=True)

    print("Loading Grounding DINO model...")
    model = load_gdino()
    print(f"Model loaded on {DEVICE}")

    # 找所有图片
    exts = [".jpg", ".jpeg", ".png", ".JPG", ".PNG"]
    image_files = []
    for root, dirs, files in os.walk(IMG_DIR):
        for f in files:
            if any(f.endswith(e) for e in exts):
                # 跳过非图片文件
                if "building_coverage" in f or "scatter" in f or "histogram" in f or "radar" in f or "urban_form" in f:
                    continue
                image_files.append(os.path.join(root, f))

    print(f"Found {len(image_files)} images")

    all_results = []
    for i, img_path in enumerate(sorted(image_files)):
        fname = os.path.basename(img_path).rsplit(".", 1)[0]
        viz_path = f"{OUT_DIR}/viz/{fname}_det.jpg"

        try:
            result = detect_image(model, img_path, viz_path)
            all_results.append(result)
        except Exception as e:
            print(f"[{i+1}/{len(image_files)}] ERROR {fname}: {e}")
            continue

        if (i + 1) % 20 == 0 or i == len(image_files) - 1:
            print(f"  Processed {i+1}/{len(image_files)}")

    # 汇总
    street_summary = {}
    for r in all_results:
        street = r["image"].split("/")[-2] if "/" in r["image"] else "unknown"
        if street not in street_summary:
            street_summary[street] = {"scores": [], "total_obstacles": 0, "categories": {}}
        street_summary[street]["scores"].append(r["accessibility_score"])
        street_summary[street]["total_obstacles"] += r["total_obstacles"]
        for cat, info in r["categories"].items():
            if cat not in street_summary[street]["categories"]:
                street_summary[street]["categories"][cat] = 0
            street_summary[street]["categories"][cat] += info["count"]

    # 计算均值
    for street, data in street_summary.items():
        scores = data["scores"]
        data["mean_score"] = sum(scores) / len(scores) if scores else 0
        data["max_score"] = max(scores) if scores else 0
        data["count"] = len(scores)
        del data["scores"]  # 精简

    # 统计障碍物类型
    cat_count = {}
    for r in all_results:
        for cat, info in r["categories"].items():
            cat_cn = OBSTACLE_CATEGORIES.get(cat, (cat, 1.0))
            cat_cn = cat_cn[0] if isinstance(cat_cn, tuple) else cat
            cat_count[cat_cn] = cat_count.get(cat_cn, 0) + info["count"]

    # 保存
    with open(f"{OUT_DIR}/detection_results.json", "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/street_summary.json", "w", encoding="utf-8") as f:
        json.dump(street_summary, f, ensure_ascii=False, indent=2)

    with open(f"{OUT_DIR}/category_stats.json", "w", encoding="utf-8") as f:
        json.dump(cat_count, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"\n=== 检测完成 ===")
    print(f"处理图片: {len(all_results)}")
    print(f"结果保存至: {OUT_DIR}/")
    print(f"\n障碍物类型统计:")
    for cat, cnt in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {cnt}")
    print(f"\n街道可达性评分 (越高=越不通畅):")
    for street, data in sorted(street_summary.items(), key=lambda x: -x[1]["mean_score"]):
        print(f"  {street}: 均值={data['mean_score']:.1f} 最大={data['max_score']:.1f} 障碍数={data['total_obstacles']}")


if __name__ == "__main__":
    main()
