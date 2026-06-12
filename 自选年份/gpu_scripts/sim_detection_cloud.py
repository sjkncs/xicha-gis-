#!/usr/bin/env python3
"""
南山区街景障碍仿真综合分析脚本
同时运行 YOLO目标检测 + FCN语义分割，生成仿真参数标注图
"""
import os, sys, json, time, re, base64, io
import numpy as np
import cv2
from PIL import Image

import torch
print(f"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")

# ===================== 模型加载 =====================
from ultralytics import YOLO

print("加载 YOLO11x...")
yolo = YOLO("yolo11x.pt")

print("加载 FCN (DeepLabV3 MobileNetV3)...")
from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large, DeepLabV3_MobileNet_V3_Large_Weights
fcn_model = deeplabv3_mobilenet_v3_large(weights=DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT)
fcn_model.eval()
if torch.cuda.is_available():
    fcn_model = fcn_model.cuda()
    print("FCN 已移至 GPU")

# Cityscapes 类别映射（用于仿真参数计算）
# 0=background, 1=ego vehicle, 2=rectification border, 3=out of roi, 4=static,
# 5=dynamic, 6=ground, 7=road, 8=sidewalk, 9=parking, 10=rail track,
# 11=building, 12=wall, 13=fence, 14=guard rail, 15=bridge, 16=tunnel,
# 17=pole, 18=pole group, 19=traffic light, 20=traffic sign, 21=vegetation,
# 22=terrain, 23=person, 24=rider, 25=car, 26=truck, 27=bus, 28=caravan,
# 29=trailer, 30=train, 31=motorcycle, 32=bicycle
CITYSCAPES_LABEL = {
    0:("背景", (0,0,0)),
    7:("道路", (128,64,128)),
    8:("人行道", (244,35,232)),
    11:("建筑", (70,70,70)),
    12:("墙体", (102,102,156)),
    13:("围栏", (190,153,153)),
    17:("立柱", (153,153,153)),
    19:("交通灯", (250,170,30)),
    20:("交通标志", (220,220,0)),
    21:("绿化", (107,142,35)),
    22:("地形", (122,160,102)),
    23:("行人", (220,20,60)),
    24:("骑行者", (255,0,0)),
    25:("汽车", (0,0,142)),
    26:("货车", (0,0,70)),
    27:("公交车", (0,60,100)),
    31:("摩托车", (119,11,32)),
    32:("自行车", (0,0,230)),
}

# 仿真参数权重（用于评分）
SIM_WEIGHTS = {
    "car": 1.2, "truck": 1.0, "bus": 0.8,
    "motorcycle": 0.9, "bicycle": 0.5, "person": 0.3,
}
ZONE_WEIGHT = {"bottom": 0.5, "middle": 0.35, "top": 0.15}

# ===================== 图片路径 =====================
IMG_DIR = "/root/autodl-tmp/streetview_analysis/images"
OUT_DIR = "/root/autodl-tmp/streetview_analysis/viz_sim"
os.makedirs(OUT_DIR, exist_ok=True)
VIZ_SAMPLES = os.path.join(OUT_DIR, "viz_sim_samples")
os.makedirs(VIZ_SAMPLES, exist_ok=True)

# ===================== 仿真参数估算函数 =====================
def estimate_road_width(mask, img_h, img_w):
    """估算道路宽度（像素），基于道路mask的左右边界"""
    road_mask = (mask == 7).astype(np.uint8)
    if road_mask.sum() == 0:
        return img_w * 0.4
    # 找底部1/4区域的左右边界
    bottom = road_mask[int(img_h * 0.75):, :]
    left_bound = np.argmax(bottom.any(axis=0))
    right_bound = img_w - 1 - np.argmax(bottom[::-1, :].any(axis=0))
    road_pix_w = max(right_bound - left_bound, 1)
    return road_pix_w / img_w

def compute_green_ratio(mask):
    """计算绿化率"""
    total = mask.size
    green_pix = np.sum((mask == 21) | (mask == 22))
    return green_pix / total

def compute_obstacle_score(detections, img_h):
    """计算障碍评分"""
    score = 0.0
    for det in detections:
        name = det["coco_name"]
        conf = det["conf"]
        y2 = det["bbox"][3]
        wt = SIM_WEIGHTS.get(name, 0.5)
        zone = "bottom" if y2 > img_h * 0.75 else ("middle" if y2 > img_h * 0.4 else "top")
        zw = ZONE_WEIGHT.get(zone, 0.2)
        score += conf * wt * zw
    return min(score * 100, 100)

def compute_passability_score(road_ratio, obstacle_score, green_ratio):
    """计算通行率"""
    # 简化公式：通行率 = 基础宽度系数 * 障碍折扣 * 绿化美化系数
    base = min(road_ratio * 2, 1.0)
    obst_penalty = 1.0 - obstacle_score / 100.0
    green_factor = 1.0 + green_ratio * 0.1
    return base * obst_penalty * green_factor

def estimate_slope(detections):
    """粗估坡度（基于画面中大物体透视消失点位置）"""
    # 简化：假设拍摄高度1.5m，焦距等效35mm -> 粗略估算
    # 实际应用需结合IMU或立体视觉
    return 0.0  # 默认平路，真实值需硬件数据

# ===================== 单图处理函数 =====================
def process_image(img_path):
    """完整处理一张图片，返回仿真参数和标注数据"""
    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        return None
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_h, img_w = img_rgb.shape[:2]

    # --- YOLO 检测 ---
    yolo_results = yolo.predict(img_path, conf=0.35, verbose=False)[0]
    detections = []
    for box in yolo_results.boxes:
        cls_id = int(box.cls.item())
        name = yolo_results.names[cls_id]
        conf = float(box.conf.item())
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        detections.append({
            "coco_id": cls_id, "coco_name": name,
            "conf": conf, "bbox": [x1, y1, x2, y2],
            "zone": "bottom" if y2 > img_h*0.75 else ("middle" if y2 > img_h*0.4 else "top"),
            "wt": SIM_WEIGHTS.get(name, 0.5),
        })

    # --- FCN 分割 ---
    inp = torch.from_numpy(img_rgb.transpose(2,0,1)).float() / 255.0
    inp = inp.unsqueeze(0)
    if torch.cuda.is_available():
        inp = inp.cuda()
    with torch.no_grad():
        out = fcn_model(inp)["out"][0].argmax(dim=0).cpu().numpy()
    seg_mask = out.astype(np.uint8)

    # --- 仿真参数计算 ---
    road_ratio = estimate_road_width(seg_mask, img_h, img_w)
    green_ratio = compute_green_ratio(seg_mask)
    obstacle_score = compute_obstacle_score(detections, img_h)
    passability = compute_passability_score(road_ratio, obstacle_score, green_ratio)
    slope_est = estimate_slope(detections)

    # --- 生成仿真标注图 ---
    annotated = draw_simulation_overlay(img_rgb, img_bgr, seg_mask, detections,
                                       road_ratio, green_ratio, obstacle_score,
                                       passability, slope_est, img_path)

    return {
        "img_path": img_path,
        "road_ratio": road_ratio,
        "green_ratio": green_ratio,
        "obstacle_score": obstacle_score,
        "passability": passability,
        "slope": slope_est,
        "detections": detections,
        "seg_mask": seg_mask,
        "annotated": annotated,
        "img_w": img_w, "img_h": img_h,
    }

def draw_simulation_overlay(img_rgb, img_bgr, seg_mask, detections,
                          road_ratio, green_ratio, obstacle_score,
                          passability, slope_est, img_path):
    """在原图上绘制仿真参数标注"""
    img_h, img_w = img_rgb.shape[:2]
    vis = img_rgb.copy()

    # 1. 语义分割叠加（低饱和度）
    overlay = np.zeros_like(img_rgb)
    for cls_id, (name, color) in CITYSCAPES_LABEL.items():
        mask = (seg_mask == cls_id)
        if mask.sum() > 0:
            overlay[mask] = color
    overlay = cv2.addWeighted(img_rgb, 0.6, overlay.astype(np.uint8), 0.4, 0)

    # 2. YOLO检测框
    for det in detections:
        if det["conf"] < 0.35:
            continue
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        name = det["coco_name"]
        color_bgr = {
            "person":(60,220,60), "car":(60,60,220),
            "motorcycle":(20,150,250), "bicycle":(20,200,50),
            "truck":(60,20,20), "bus":(100,30,30),
        }.get(name, (100,100,100))
        cv2.rectangle(overlay, (x1,y1), (x2,y2), color_bgr, 2)
        # 标签
        cn_map = {
            "person":"行人", "car":"汽车", "motorcycle":"摩托车",
            "bicycle":"自行车", "truck":"货车", "bus":"公交车",
            "bench":"长椅", "stop sign":"停车标志",
        }
        label = f"{cn_map.get(name, name)} {det['conf']:.0%}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(overlay, (x1, y1-lh-8), (x1+lw+8, y1), color_bgr, -1)
        cv2.putText(overlay, label, (x1+4, y1-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2)

    # 3. 仿真参数信息面板（右上角）
    panel_x, panel_y = img_w - 10, 10
    panel_bg = np.zeros((260, 320, 3), dtype=np.uint8) + 255

    def put_panel_text(img, y, text, font=cv2.FONT_HERSHEY_SIMPLEX, fscale=0.7, thick=2, color=(30,30,30)):
        cv2.putText(img, text, (panel_x - 310, panel_y + y),
                    font, fscale, color, thick)
        return y + int(32 * fscale) + 8

    y_off = 25
    y_off = put_panel_text(panel_bg, y_off, "=== 仿真参数 ===", 0.8, 2, (20,80,180))
    y_off = put_panel_text(panel_bg, y_off, f"道路占有率: {road_ratio:.1%}", 0.7, 2)
    y_off = put_panel_text(panel_bg, y_off, f"绿化覆盖率: {green_ratio:.1%}", 0.7, 2)
    y_off = put_panel_text(panel_bg, y_off, f"障碍评分:   {obstacle_score:.1f}", 0.7, 2)
    y_off = put_panel_text(panel_bg, y_off, f"通行率:     {passability:.1%}", 0.7, 2)
    y_off = put_panel_text(panel_bg, y_off, f"估算坡度:   {slope_est:.1f}deg", 0.7, 2)
    y_off += 5
    y_off = put_panel_text(panel_bg, y_off, "--- 障碍物统计 ---", 0.7, 2, (180,60,20))
    cat_counts = {}
    for d in detections:
        n = d["coco_name"]
        cat_counts[n] = cat_counts.get(n, 0) + 1
    for n, cnt in sorted(cat_counts.items(), key=lambda x:-x[1]):
        y_off = put_panel_text(panel_bg, y_off, f"  {n}({cnt})", 0.65, 1)

    # 评分颜色
    if obstacle_score >= 60: sc = (30,30,220)
    elif obstacle_score >= 40: sc = (30,120,220)
    elif obstacle_score >= 20: sc = (30,180,220)
    else: sc = (30,200,30)
    cv2.rectangle(panel_bg, (5,5), (315,260), sc, 3)

    overlay[panel_y:panel_y+260, panel_x-320:panel_x] = panel_bg

    # 4. 标注分类图例（左下角）
    legend_items = [
        ("汽车", (60,60,220)),
        ("行人", (60,220,60)),
        ("摩托车", (20,150,250)),
        ("货车", (60,20,20)),
        ("道路", (128,64,128)),
        ("绿化", (107,142,35)),
        ("人行道", (244,35,232)),
    ]
    lx, ly = 10, img_h - 20
    lbg_h = len(legend_items) * 22 + 10
    lbg = np.zeros((lbg_h, 150, 3), dtype=np.uint8) + 200
    for i, (lbl, col) in enumerate(legend_items):
        cv2.rectangle(lbg, (5, i*22+3), (25, i*22+18), col, -1)
        cv2.putText(lbg, lbl, (30, i*22+15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20,20,20), 1)
    overlay[ly-lbg_h:ly, lx:lx+150] = lbg

    return cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)

# ===================== 主循环：处理南山区所有图片 =====================
results_all = []

# 南山区所有子目录
district = "南山区"
district_dir = os.path.join(IMG_DIR, district)
if not os.path.exists(district_dir):
    print(f"目录不存在: {district_dir}")
    sys.exit(1)

print(f"扫描 {district_dir} ...")
all_imgs = []
for root, dirs, files in os.walk(district_dir):
    for fn in files:
        if fn.endswith(".jpg") and not fn.startswith("."):
            all_imgs.append(os.path.join(root, fn))

print(f"共找到 {len(all_imgs)} 张图片")
if not all_imgs:
    sys.exit(1)

# 处理前50张（防止超时）
all_imgs = all_imgs[:50]
print(f"处理前 {len(all_imgs)} 张...")

for i, img_path in enumerate(all_imgs, 1):
    rel = os.path.relpath(img_path, IMG_DIR)
    print(f"[{i}/{len(all_imgs)}] {rel[:60]}...", end=" ", flush=True)
    t0 = time.time()
    result = process_image(img_path)
    if result:
        results_all.append(result)
        # 保存标注图
        out_fn = rel.replace(os.sep, "_").replace(":", "_") + ".png"
        out_path = os.path.join(VIZ_SAMPLES, out_fn)
        cv2.imwrite(out_path, result["annotated"])
        print(f"障碍{result['obstacle_score']:.1f} 通行{result['passability']:.1%} ({time.time()-t0:.1f}s)")
    else:
        print(f"失败")

print(f"\n完成！共处理 {len(results_all)} 张图片")
print(f"标注图保存在: {VIZ_SAMPLES}")

# ===================== 保存JSON结果 =====================
json_out = os.path.join(OUT_DIR, "sim_results.json")
save_data = []
for r in results_all:
    save_data.append({
        "image": r["img_path"],
        "road_ratio": round(r["road_ratio"], 4),
        "green_ratio": round(r["green_ratio"], 4),
        "obstacle_score": round(float(r["obstacle_score"]), 2),
        "passability": round(float(r["passability"]), 4),
        "slope": round(float(r["slope"]), 2),
        "n_detections": len(r["detections"]),
        "detections": r["detections"],
        "annotated_png": os.path.join(VIZ_SAMPLES, os.path.relpath(r["img_path"], IMG_DIR).replace(os.sep, "_") + ".png"),
    })

with open(json_out, "w", encoding="utf-8") as f:
    json.dump(save_data, f, ensure_ascii=False, indent=2)
print(f"结果JSON: {json_out}")

# ===================== 汇总统计 =====================
if results_all:
    scores = [r["obstacle_score"] for r in results_all]
    roads  = [r["road_ratio"] for r in results_all]
    greens = [r["green_ratio"] for r in results_all]
    passes = [r["passability"] for r in results_all]
    print(f"\n===== 仿真参数汇总 (n={len(results_all)}) =====")
    print(f"障碍评分  均值={np.mean(scores):.1f}  中位={np.median(scores):.1f}  范围=[{np.min(scores):.1f},{np.max(scores):.1f}]")
    print(f"道路占有率  均值={np.mean(roads):.1%}  中位={np.median(roads):.1%}")
    print(f"绿化覆盖率  均值={np.mean(greens):.1%}  中位={np.median(greens):.1%}")
    print(f"通行率    均值={np.mean(passes):.1%}  中位={np.median(passes):.1%}")

    # 街道级统计
    by_street = {}
    for r in results_all:
        parts = r["img_path"].split("/")
        if len(parts) >= 7 and parts[-5] == district:
            street = parts[-4]
            if street not in by_street:
                by_street[street] = []
            by_street[street].append(r)

    print(f"\n===== 街道级仿真参数 =====")
    for street, recs in sorted(by_street.items()):
        s = [r["obstacle_score"] for r in recs]
        p = [r["passability"] for r in recs]
        g = [r["green_ratio"] for r in recs]
        print(f"  {street:6s}: n={len(recs):2d}  障碍={np.mean(s):5.1f}  通行={np.mean(p):5.1%}  绿化={np.mean(g):5.1%}")
