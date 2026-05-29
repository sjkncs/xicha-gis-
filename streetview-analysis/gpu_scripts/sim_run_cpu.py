#!/usr/bin/env python3
"""南山区街景综合分析 - CPU模式（支持中文字体标注）"""
import os, sys, time, json, math
import numpy as np
import cv2
import torch

print("PyTorch:", torch.__version__, "CUDA:", torch.cuda.is_available())

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

# ==================== 中文字体支持 ====================
from PIL import Image, ImageDraw, ImageFont

def _get_font(size=20):
    """加载可用的中文字体"""
    for fp in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/simkai.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()

_FONT_PANEL = _get_font(18)
_FONT_BIG   = _get_font(22)
_FONT_SMALL = _get_font(14)
_FONT_TINY  = _get_font(12)

def _pil_text(draw, pos, text, font, color_rgb):
    """在 PIL ImageDraw 上写文本，支持中文"""
    draw.text(pos, text, font=font, fill=color_rgb)

def _render_to_numpy(pil_img):
    """PIL RGBA -> numpy BGR (用于和 OpenCV 混用)"""
    arr = np.array(pil_img)
    if arr.shape[2] == 4:
        arr = arr[:, :, :3]
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

CITYSCAPES = {
    0: ("背景", (0, 0, 0)),
    7: ("道路", (128, 64, 128)),
    8: ("人行道", (244, 35, 232)),
    11: ("建筑", (70, 70, 70)),
    12: ("墙体", (102, 102, 156)),
    13: ("围栏", (190, 153, 153)),
    17: ("立柱", (153, 153, 153)),
    19: ("交通灯", (250, 170, 30)),
    20: ("标志牌", (220, 220, 0)),
    21: ("绿化", (107, 142, 35)),
    22: ("地形", (122, 160, 102)),
    23: ("行人", (220, 20, 60)),
    24: ("骑行者", (255, 0, 0)),
    25: ("汽车", (0, 0, 142)),
    26: ("货车", (0, 0, 70)),
    27: ("公交车", (0, 60, 100)),
    31: ("摩托车", (119, 11, 32)),
    32: ("自行车", (0, 0, 230)),
}

COCO_CN = {
    "person": "行人", "car": "汽车", "motorcycle": "摩托车",
    "bicycle": "自行车", "truck": "货车", "bus": "公交车",
    "bench": "长椅", "stop sign": "停车标志", "fire hydrant": "消防栓",
    "traffic light": "交通灯",
}

BOX_COLORS = {
    "person": (60, 220, 60), "car": (60, 60, 220),
    "motorcycle": (20, 150, 250), "bicycle": (20, 200, 50),
    "truck": (60, 20, 20), "bus": (100, 30, 30),
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


def annotate(img_rgb, mask, dets, r_ratio, g_ratio, obs, passab, coords):
    h, w = img_rgb.shape[:2]

    # ---- OpenCV 部分：分割叠加 + 检测框 ----
    overlay = np.zeros_like(img_rgb, dtype=np.uint8)
    for cid, (name, color) in CITYSCAPES.items():
        m = (mask == cid)
        if m.sum() > 0:
            overlay[m] = color
    vis = cv2.addWeighted(img_rgb, 0.55, overlay.astype(np.uint8), 0.45, 0)

    # YOLO bounding boxes（用 OpenCV，英文标签）
    for det in dets:
        if det["conf"] < 0.35:
            continue
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        name = det["coco_name"]
        color = BOX_COLORS.get(name, (100, 100, 100))
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
        label_en = f"{COCO_CN.get(name, name)} {det['conf']:.0%}"
        (tw, th), _ = cv2.getTextSize(label_en, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
        cv2.rectangle(vis, (x1, y1 - th - 10), (x1 + tw + 8, y1), color, -1)
        cv2.putText(vis, label_en, (x1 + 4, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    # ---- PIL 部分：右侧面板 + 图例（支持中文） ----
    pil_vis = Image.fromarray(vis)
    draw = ImageDraw.Draw(pil_vis)

    # ---- 仿真参数面板（右侧） ----
    pw, ph = 300, 320
    panel_pil = Image.new("RGBA", (pw, ph), (245, 250, 255, 230))
    pd = ImageDraw.Draw(panel_pil)
    if obs >= 60:
        border = (0, 0, 220)
    elif obs >= 40:
        border = (0, 120, 220)
    elif obs >= 20:
        border = (0, 180, 220)
    else:
        border = (0, 200, 80)
    pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*border, 255), width=3)
    y_pos = 10

    def put_panel(txt, fs=14, bold=False, fc=(30, 30, 30)):
        nonlocal y_pos
        fnt = _FONT_SMALL if fs <= 12 else (_FONT_BIG if fs >= 18 else _FONT_PANEL)
        pd.text((8, y_pos), txt, font=fnt, fill=(*fc, 255))
        y_pos += fs + 8

    put_panel("=== 仿真参数 ===", 18, fc=(20, 80, 180))
    put_panel(f"道路比率: {r_ratio:.1%}", fc=(30, 30, 30))
    put_panel(f"绿化覆盖: {g_ratio:.1%}", fc=(30, 30, 30))
    put_panel(f"障碍评分: {obs:.1f}", fc=(30, 30, 30))
    put_panel(f"通行率:   {passab:.1%}", fc=(30, 30, 30))
    y_pos += 4
    put_panel("--- 检测统计 ---", 12, fc=(180, 60, 20))
    cc = {}
    for d in dets:
        n = d["coco_name"]
        cc[n] = cc.get(n, 0) + 1
    for n, cnt in sorted(cc.items(), key=lambda x: -x[1]):
        cn_label = COCO_CN.get(n, n)
        put_panel(f"  {cn_label}({cnt})", 11, fc=(60, 60, 60))

    pil_vis.paste(panel_pil, (w - pw, 0))

    # ---- 图例（左下角） ----
    legend_items = [
        ("汽车", (60, 60, 220)),
        ("行人", (60, 220, 60)),
        ("摩托车", (20, 150, 250)),
        ("货车", (60, 20, 20)),
        ("道路", (128, 64, 128)),
        ("绿化", (107, 142, 35)),
        ("人行道", (244, 35, 232)),
    ]
    lh_val = len(legend_items) * 26 + 8
    lw_val = 155
    lbg = Image.new("RGBA", (lw_val, lh_val), (220, 220, 220, 230))
    ld = ImageDraw.Draw(lbg)
    for i, (lbl, col) in enumerate(legend_items):
        r, g, b = col
        ld.rectangle([5, i * 26 + 3, 22, i * 26 + 17], fill=(r, g, b, 255))
        ld.text((28, i * 26 + 1), lbl, font=_FONT_TINY, fill=(20, 20, 20, 255))
    lx, ly = 5, h - lh_val - 5
    if ly >= 0:
        pil_vis.paste(lbg, (lx, ly), mask=lbg)

    # ---- 坐标标注（左下角下方） ----
    draw.text((8, h - 24), coords[:30], font=_FONT_TINY, fill=(255, 255, 255, 255))

    # ---- 转换回 BGR ----
    final = np.array(pil_vis)
    if final.shape[2] == 4:
        final = final[:, :, :3]
    return cv2.cvtColor(final, cv2.COLOR_RGB2BGR)



IMG_ROOT = "/root/autodl-tmp/streetview_images"
OUT_ROOT = "/root/autodl-tmp/streetview_sim"
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
imgs = imgs[:30]
results = []

for i, img_path in enumerate(imgs, 1):
    coords = os.path.basename(os.path.dirname(img_path))
    sys.stdout.write("[%d/%d] %s... " % (i, len(imgs), coords[:20]))
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

    ann = annotate(img_rgb, seg, dets, rr, gr, obs, pas, coords)
    out_fn = coords + ".jpg"
    cv2.imwrite(os.path.join(SAMPLES, out_fn), ann, [cv2.IMWRITE_JPEG_QUALITY, 92])

    results.append({
        "image": img_path,
        "coords": coords,
        "road_ratio": round(rr, 4),
        "green_ratio": round(gr, 4),
        "obstacle_score": round(float(obs), 2),
        "passability": round(float(pas), 4),
        "n_dets": len(dets),
    })
    sys.stdout.write("obs=%.1f pass=%.1f%% (%.1fs)\n" % (obs, pas * 100, time.time() - t0))
    sys.stdout.flush()

print("\nDone! %d images processed" % len(results))

json_out = os.path.join(OUT_ROOT, "sim_results.json")
with open(json_out, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

scores = [r["obstacle_score"] for r in results]
print("\n=== SUMMARY ===")
print("Obstacle: mean=%.1f med=%.1f range=[%.1f,%.1f]" % (
    np.mean(scores), np.median(scores), np.min(scores), np.max(scores)))
print("Road Ratio: %.1f%%" % (np.mean([r["road_ratio"] for r in results]) * 100))
print("Green Cover: %.1f%%" % (np.mean([r["green_ratio"] for r in results]) * 100))
print("Passability: %.1f%%" % (np.mean([r["passability"] for r in results]) * 100))
