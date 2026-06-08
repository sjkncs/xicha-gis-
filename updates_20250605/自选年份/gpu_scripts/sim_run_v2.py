#!/usr/bin/env python3
"""南山区街景综合分析 v2 - 修复文件名+处理全部图片"""
import os, sys, time, json
import numpy as np
import cv2
import torch

import subprocess
for pkg in ["ultralytics"]:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--quiet", pkg], capture_output=True)
    print(pkg, ":", "OK" if r.returncode == 0 else "FAIL")

from ultralytics import YOLO
print("Loading YOLO11x...")
yolo = YOLO("yolo11x.pt")

from torchvision.models.segmentation import deeplabv3_mobilenet_v3_large, DeepLabV3_MobileNet_V3_Large_Weights
print("Loading DeepLabV3...")
fcn = deeplabv3_mobilenet_v3_large(weights=DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT)
fcn.eval()
print("Models loaded OK")

CITYSCAPES = {
    0:("bkg", (0, 0, 0)),
    7:("road", (128, 64, 128)),
    8:("sidewalk", (244, 35, 232)),
    11:("building", (70, 70, 70)),
    12:("wall", (102, 102, 156)),
    13:("fence", (190, 153, 153)),
    17:("pole", (153, 153, 153)),
    19:("traffic_light", (250, 170, 30)),
    20:("traffic_sign", (220, 220, 0)),
    21:("vegetation", (107, 142, 35)),
    22:("terrain", (122, 160, 102)),
    23:("person", (220, 20, 60)),
    24:("rider", (255, 0, 0)),
    25:("car", (0, 0, 142)),
    26:("truck", (0, 0, 70)),
    27:("bus", (0, 60, 100)),
    31:("motorcycle", (119, 11, 32)),
    32:("bicycle", (0, 0, 230)),
}

COCO_CN = {
    "person": "P-行人",
    "car": "C-汽车",
    "motorcycle": "M-摩托车",
    "bicycle": "B-自行车",
    "truck": "T-货车",
    "bus": "Bus-公交",
    "bench": "Bench-长椅",
    "stop sign": "Sign-停",
    "fire hydrant": "Hydrant-消防",
    "traffic light": "TL-交通灯",
}

BOX_COLORS = {
    "person": (60, 220, 60),
    "car": (60, 60, 220),
    "motorcycle": (20, 150, 250),
    "bicycle": (20, 200, 50),
    "truck": (60, 20, 20),
    "bus": (100, 30, 30),
    "bench": (180, 100, 180),
}

SIM_W = {
    "car": 1.2, "truck": 1.0, "bus": 0.8,
    "motorcycle": 0.9, "bicycle": 0.5, "person": 0.3,
}
ZONE_W = {"bottom": 0.5, "middle": 0.35, "top": 0.15}


def road_ratio(mask, h, w):
    road = (mask == 7).astype(float)
    if road.sum() == 0:
        return 0.4
    bottom = road[int(h * 0.75):, :]
    lc = int(np.argmax(bottom.any(axis=0)))
    rc = int(w - 1 - np.argmax(bottom[::-1, :].any(axis=0)))
    return max(rc - lc, 1) / float(w)


def green_ratio(mask):
    total_pix = float(mask.size)
    green_pix = float(np.sum((mask == 21) | (mask == 22)))
    return green_pix / total_pix


def obstacle_score(dets, h):
    total = 0.0
    for d in dets:
        wt = SIM_W.get(d["coco_name"], 0.5)
        y2 = d["bbox"][3]
        if y2 > h * 0.75:
            zone = "bottom"
        elif y2 > h * 0.4:
            zone = "middle"
        else:
            zone = "top"
        zw = ZONE_W.get(zone, 0.2)
        total += d["conf"] * wt * zw
    return min(total * 100, 100)


def passability(r_ratio, obs_score, g_ratio):
    base = min(r_ratio * 2, 1.0)
    return base * (1 - obs_score / 100.0) * (1 + g_ratio * 0.1)


def annotate(img_rgb, mask, dets, r_ratio, g_ratio, obs, passab, coords, direction):
    h, w = img_rgb.shape[:2]
    vis = img_rgb.copy()

    # Semantic segmentation overlay
    overlay = np.zeros_like(img_rgb, dtype=np.uint8)
    for cid, (name, color) in CITYSCAPES.items():
        m = (mask == cid)
        if m.sum() > 0:
            overlay[m] = color
    vis = cv2.addWeighted(vis, 0.55, overlay.astype(np.uint8), 0.45, 0)

    # YOLO bounding boxes
    for det in dets:
        if det["conf"] < 0.35:
            continue
        x1 = int(det["bbox"][0])
        y1 = int(det["bbox"][1])
        x2 = int(det["bbox"][2])
        y2 = int(det["bbox"][3])
        name = det["coco_name"]
        color = BOX_COLORS.get(name, (100, 100, 100))
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label = COCO_CN.get(name, name) + " %.0f%%" % (det["conf"] * 100)
        tw2, th2 = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
        cv2.rectangle(vis, (x1, y1 - th2 - 10), (x1 + tw2 + 8, y1), color, -1)
        cv2.putText(vis, label, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Simulation parameter panel (right side)
    pw, ph = 300, 300
    panel = np.full((ph, pw, 3), 255, dtype=np.uint8)
    if obs >= 60:
        pc = (0, 0, 220)
    elif obs >= 40:
        pc = (0, 120, 220)
    elif obs >= 20:
        pc = (0, 180, 220)
    else:
        pc = (0, 200, 80)
    cv2.rectangle(panel, (2, 2), (pw - 3, ph - 3), pc, 3)
    y_pos = 28

    def put_text(txt, fs=0.7, c=(30, 30, 30)):
        nonlocal y_pos
        cv2.putText(panel, txt, (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, fs, c, 2)
        y_pos += int(28 * fs) + 6

    put_text("=== SIMULATION PARAMS ===", 0.85, (20, 80, 180))
    put_text("Road Ratio:   %.1f%%" % (r_ratio * 100))
    put_text("Green Cover:  %.1f%%" % (g_ratio * 100))
    put_text("Obstacle:     %.1f" % obs)
    put_text("Passability:  %.1f%%" % (passab * 100))
    y_pos += 5
    put_text("--- Detection Stats ---", 0.7, (180, 60, 20))
    cc = {}
    for d in dets:
        n = d["coco_name"]
        cc[n] = cc.get(n, 0) + 1
    for n, cnt in sorted(cc.items(), key=lambda x: -x[1]):
        cn_label = COCO_CN.get(n, n)
        put_text("  %s(%d)" % (cn_label, cnt), 0.65, (60, 60, 60))
    vis[0:ph, w - pw:w] = panel

    # Legend (bottom left)
    legend_items = [
        ("C-Car 汽车", (60, 60, 220)),
        ("P-Person 行人", (60, 220, 60)),
        ("M-Moto 摩托车", (20, 150, 250)),
        ("T-Truck 货车", (60, 20, 20)),
        ("Road 道路", (128, 64, 128)),
        ("Green 绿化", (107, 142, 35)),
        ("Walk 人行道", (244, 35, 232)),
    ]
    lh_val = len(legend_items) * 24 + 12
    lw_val = 180
    lbg = np.full((lh_val, lw_val, 3), 220, dtype=np.uint8)
    for i, (lbl, col) in enumerate(legend_items):
        cv2.rectangle(lbg, (5, i * 24 + 4), (22, i * 24 + 18), col, -1)
        cv2.putText(lbg, lbl, (28, i * 24 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1)
    lx = 5
    ly = h - lh_val - 5
    if ly >= 0:
        vis[ly:ly + lh_val, lx:lx + lw_val] = lbg

    # Coordinates + direction label
    label_text = coords + " " + direction
    cv2.putText(vis, label_text[:35], (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    return cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)


IMG_ROOT = "/root/autodl-tmp/streetview_images"
OUT_ROOT = "/root/autodl-tmp/streetview_sim_v2"
os.makedirs(OUT_ROOT, exist_ok=True)
SAMPLES = os.path.join(OUT_ROOT, "samples")
os.makedirs(SAMPLES, exist_ok=True)

nanshan_dir = os.path.join(IMG_ROOT, "南山区")
imgs = []
for root, dirs, files in os.walk(nanshan_dir):
    for fn in files:
        if fn.endswith(".jpg") and not fn.startswith("."):
            imgs.append(os.path.join(root, fn))

print("Nanshan images:", len(imgs))
imgs = imgs[:60]  # Process 60 images
results = []

for i, img_path in enumerate(imgs, 1):
    # Get direction from filename
    fn_base = os.path.basename(img_path)
    parts = fn_base.replace(".jpg", "").split("_")
    direction = parts[-2] if len(parts) >= 2 else "UNK"
    coords = os.path.basename(os.path.dirname(img_path))
    # Use full basename as output filename to avoid collisions
    out_fn = fn_base.replace(".jpg", "_annotated.jpg")
    
    sys.stdout.write("[%d/%d] %s_%s... " % (i, len(imgs), coords[:15], direction))
    sys.stdout.flush()
    t0 = time.time()

    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        print("READ FAIL")
        continue
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    ih, iw = img_rgb.shape[:2]

    # YOLO detection (CPU)
    dets = []
    for box in yolo.predict(img_path, conf=0.35, verbose=False, device="cpu")[0].boxes:
        cid = int(box.cls.item())
        name = yolo.names[cid]
        conf = float(box.conf.item())
        x1 = float(box.xyxy[0][0].item())
        y1 = float(box.xyxy[0][1].item())
        x2 = float(box.xyxy[0][2].item())
        y2 = float(box.xyxy[0][3].item())
        dets.append({"coco_name": name, "conf": conf, "bbox": [x1, y1, x2, y2]})

    # FCN semantic segmentation (CPU)
    img_chw = img_rgb.transpose(2, 0, 1)
    inp = torch.from_numpy(img_chw).float() / 255.0
    inp = inp.unsqueeze(0)
    with torch.no_grad():
        out = fcn(inp)["out"][0]
        seg = out.argmax(dim=0).numpy().astype(np.uint8)

    rr = road_ratio(seg, ih, iw)
    gr = green_ratio(seg)
    obs = obstacle_score(dets, ih)
    pas = passability(rr, obs, gr)

    ann = annotate(img_rgb, seg, dets, rr, gr, obs, pas, coords, direction)
    cv2.imwrite(os.path.join(SAMPLES, out_fn), ann, [cv2.IMWRITE_JPEG_QUALITY, 92])

    results.append({
        "image": img_path,
        "coords": coords,
        "direction": direction,
        "road_ratio": round(rr, 4),
        "green_ratio": round(gr, 4),
        "obstacle_score": round(float(obs), 2),
        "passability": round(float(pas), 4),
        "n_dets": len(dets),
        "detections": dets,
        "annotated": os.path.join(SAMPLES, out_fn),
    })
    sys.stdout.write("obs=%.1f pass=%.1f%% (%.1fs)\n" % (obs, pas * 100, time.time() - t0))
    sys.stdout.flush()

print("\nDone! %d images processed" % len(results))

json_out = os.path.join(OUT_ROOT, "sim_results_v2.json")
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

scores = [r["obstacle_score"] for r in results]
print("\n=== SUMMARY ===")
print("Obstacle: mean=%.1f med=%.1f range=[%.1f,%.1f]" % (
    np.mean(scores), np.median(scores), np.min(scores), np.max(scores)))
print("Road Ratio: %.1f%%" % (np.mean([r["road_ratio"] for r in results]) * 100))
print("Green Cover: %.1f%%" % (np.mean([r["green_ratio"] for r in results]) * 100))
print("Passability: %.1f%%" % (np.mean([r["passability"] for r in results]) * 100))

# By direction
for d in ["N", "E", "S", "W"]:
    sub = [r for r in results if r["direction"] == d]
    if sub:
        s = [r["obstacle_score"] for r in sub]
        p = [r["passability"] for r in sub]
        print("Dir %s: n=%d obs=%.1f pass=%.1f%%" % (d, len(sub), np.mean(s), np.mean(p) * 100))
