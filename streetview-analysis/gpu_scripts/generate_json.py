#!/usr/bin/env python3
"""只生成JSON结果（从已处理的viz图片重新汇总）"""
import os, json, time, warnings
os.environ["YOLO_VERBOSE"] = "False"
warnings.filterwarnings("ignore")

import numpy as np
import cv2
import torch
from ultralytics import YOLO

REMOTE_DIR  = "/root/autodl-tmp/streetview_analysis"
IMG_DIR     = f"{REMOTE_DIR}/images"
OUT_DIR    = f"{REMOTE_DIR}/yolo_obstacle_results"
MODEL_PATH = f"{REMOTE_DIR}/yolo_models/yolo11x.pt"
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"

COCO_MAP = {
    0: ("person",        "行人/使用者",    1.5),
    1: ("bicycle",       "自行车占道",      1.5),
    2: ("car",           "汽车占道",        2.0),
    3: ("motorcycle",    "摩托车/电动车",   1.5),
    5: ("bus",           "公交车占道",      2.0),
    7: ("truck",         "货车占道",        2.0),
    11:("stop sign",     "停车标志",        0.3),
    13:("bench",         "长椅占道",        1.5),
    14:("backpack",      "背包",           0.3),
    24:("backpack",      "背包",           0.3),
}
AREA_W = {"bottom": 0.50, "middle": 0.35, "top": 0.15}

def classify_view(p):
    p_lower = p.lower()
    kw_ground = ["step","stairs","stair","ramp","盲道","台阶","楼梯"]
    for k in kw_ground:
        if k in p_lower:
            return "ground_view"
    if "_U_" in p:
        return "ground_view"
    return "street_view"

def get_zone(y1n):
    if y1n > 0.65: return "bottom"
    if y1n > 0.35: return "middle"
    return "top"

def to_json_friendly(obj):
    """convert numpy/float32 types to JSON-safe native Python types"""
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, list):
        return [to_json_friendly(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_json_friendly(v) for k, v in obj.items()}
    return obj

print("Loading yolo11x...", flush=True)
m = YOLO(MODEL_PATH)
m.to(DEVICE)
print("Model ready.", flush=True)

skip = {"building","scatter","histogram","radar","urban_form",
        "obstacle","heatmap","category_bar","score_dist","fcn"}
imgs = []
for r, ds, fs in os.walk(IMG_DIR):
    for f in fs:
        if (f.endswith(".jpg") or f.endswith(".JPG") or f.endswith(".png")):
            if not any(s in f for s in skip):
                imgs.append(os.path.join(r, f))
imgs = sorted(imgs)
print(f"Found {len(imgs)} images", flush=True)

all_results = []
t0 = time.time()
for i, img_path in enumerate(imgs):
    try:
        img = cv2.imread(img_path)
        if img is None:
            continue
        h, w = img.shape[:2]
        vt = classify_view(img_path)
        rs = m.predict(img_path, conf=0.35, iou=0.45, verbose=False, device=DEVICE)

        dets = []
        if rs and rs[0].boxes is not None:
            boxes = rs[0].boxes
            for j in range(len(boxes)):
                cid = int(boxes.cls[j].item())
                if cid not in COCO_MAP:
                    continue
                conf = float(boxes.conf[j].item())
                x1, y1, x2, y2 = boxes.xyxy[j].cpu().numpy()
                x1n, y1n = float(x1/w), float(y1/h)
                x2n, y2n = float(x2/w), float(y2/h)
                cn, cn_label, wt = COCO_MAP[cid]
                zone = get_zone(y1n)
                comp = conf * wt * AREA_W[zone]
                bw, bh = x2-x1, y2-y1
                if bw < 8 or bh < 8 or bw > w*0.95 or bh > h*0.95:
                    continue
                dets.append({
                    "coco_id": cid,
                    "coco_name": cn,
                    "cn_label": cn_label,
                    "conf": round(float(conf), 3),
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "bbox_norm": [round(x1n, 4), round(y1n, 4), round(x2n, 4), round(y2n, 4)],
                    "zone": zone,
                    "wt": float(wt),
                    "comp": round(float(comp), 4),
                })

        cats = {}
        for d in dets:
            cats[d["cn_label"]] = cats.get(d["cn_label"], 0) + 1
        score = min(100.0, sum(d["comp"] for d in dets) * 10)

        result = {
            "image": img_path,
            "view_type": vt,
            "detections": dets,
            "total_obstacles": len(dets),
            "accessibility_score": round(float(score), 2),
            "categories": cats,
        }
        all_results.append(result)
    except Exception as e:
        print(f"ERR [{i+1}/{len(imgs)}] {os.path.basename(img_path)}: {e}", flush=True)

    if (i+1) % 20 == 0 or i == len(imgs)-1:
        el = time.time() - t0
        rate = (i+1)/el if el > 0 else 0
        eta = (len(imgs)-i-1)/rate if rate > 0 else 0
        print(f"  {i+1}/{len(imgs)} Elapsed:{el:.0f}s ETA:{eta:.0f}s", flush=True)

# 街道统计
streets = {}
for r in all_results:
    parts = r["image"].split(os.sep)
    st = parts[-4] if len(parts) >= 4 else "unknown"
    if st not in streets:
        streets[st] = {"count":0,"scores":[],"n_obs":0,
                        "vt":{"street_view":0,"ground_view":0},"cats":{}}
    streets[st]["count"] += 1
    streets[st]["scores"].append(r["accessibility_score"])
    streets[st]["n_obs"] += r["total_obstacles"]
    streets[st]["vt"][r["view_type"]] += 1
    for k, v in r["categories"].items():
        streets[st]["cats"][k] = streets[st]["cats"].get(k, 0) + v
for st, data in streets.items():
    sc = data["scores"]
    data["mean_score"] = round(sum(sc)/len(sc), 2) if sc else 0.0
    data["max_score"] = round(max(sc), 2) if sc else 0.0
    data["min_score"] = round(min(sc), 2) if sc else 0.0
    del data["scores"]

# 全局类别
gcats = {}
for r in all_results:
    for k, v in r["categories"].items():
        gcats[k] = gcats.get(k, 0) + v

# 视角统计
sv = sum(1 for r in all_results if r["view_type"]=="street_view")
gv = len(all_results) - sv
tt = time.time() - t0

# 全部转为JSON安全类型
all_results_safe = to_json_friendly(all_results)
streets_safe    = to_json_friendly(streets)
gcats_safe     = to_json_friendly(gcats)

# 保存
print("Saving JSON...", flush=True)
with open(f"{OUT_DIR}/all_results.json", "w", encoding="utf-8") as f:
    json.dump(all_results_safe, f, ensure_ascii=False, indent=2)
with open(f"{OUT_DIR}/street_stats.json", "w", encoding="utf-8") as f:
    json.dump(streets_safe, f, ensure_ascii=False, indent=2)
with open(f"{OUT_DIR}/global_categories.json", "w", encoding="utf-8") as f:
    json.dump(gcats_safe, f, ensure_ascii=False, indent=2)

print()
print("="*65)
print("SUMMARY")
print("="*65)
print(f"Images: {len(all_results)} ({sv} street_view, {gv} ground_view)")
print(f"Time: {tt:.0f}s ({tt/len(all_results):.2f}s/img)")
print()
print("Global categories:")
for cat, cnt in sorted(gcats_safe.items(), key=lambda x: -x[1]):
    print(f"  {cat}: {cnt}")
print()
print("Street accessibility (mean score, higher=more obstacles):")
for st, data in sorted(streets_safe.items(), key=lambda x: -x[1]["mean_score"]):
    print(f"  {st}: mean={data['mean_score']} max={data['max_score']} "
          f"obs={data['n_obs']} imgs={data['count']}")
print()
print(f"Output: {OUT_DIR}/")
print("  all_results.json, street_stats.json, global_categories.json")
