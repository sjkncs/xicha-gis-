#!/usr/bin/env python3
"""seg_inference_v6.py - Fixed model loading via from_pretrained with local path."""
import os, sys, json, time, traceback
import numpy as np
from pathlib import Path
from PIL import Image
import torch
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

# ====== 配置 ======
DATA_DIR = Path("/root/autodl-tmp/streetview_analysis/images")
MODEL_DIR = Path("/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default")
OUT_DIR = Path("/root/autodl-tmp/outputs/segmentation")
CKPT_FILE = OUT_DIR / "checkpoint.json"
OUT_CSV = OUT_DIR / "seg_results.csv"

# ====== 类别映射 (ADE20K 150类 -> 7个指标) ======
CITY_CLASSES = {
    0: ("road",  "road"),
    1: ("sidewalk", "road"),
    2: ("building", "building"),
    3: ("wall",     "building"),
    5: ("fence",    "other"),
    6: ("pole",     "other"),
    7: ("traffic_light", "other"),
    8: ("traffic_sign",  "other"),
    9: ("vegetation",     "green"),
    10: ("terrain",       "green"),
    11: ("sky",           "sky"),
    12: ("person",        "person"),
    13: ("rider",         "person"),
    14: ("car",           "car"),
    15: ("truck",         "car"),
    16: ("bus",           "car"),
    17: ("train",         "car"),
    18: ("motorcycle",    "car"),
    19: ("bicycle",       "car"),
}

COLOR_MAP = {
    "building": (230, 100, 50),
    "road":     (128, 128, 128),
    "green":    (50, 180, 50),
    "sky":      (135, 206, 250),
    "person":   (255, 105, 180),
    "car":      (255, 200, 100),
    "other":    (220, 220, 220),
}

CITY_KEYS = ["building", "road", "green", "sky", "person", "car", "other"]

# ====== 模型加载 ======
def load_model():
    snap_dir = str(MODEL_DIR)
    print(f"Loading model from: {snap_dir}")
    processor = AutoImageProcessor.from_pretrained(snap_dir, local_files_only=True)
    model = AutoModelForSemanticSegmentation.from_pretrained(snap_dir, local_files_only=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    print(f"Model loaded. Device: {device}, CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    return model, processor, device

# ====== 图像处理 (等距矩形 -> 6视角) ======
def equirectangular_to_perspective(img, fov=90, yaw=0, pitch=0, W_out=512, H_out=512):
    """将等距矩形全景图投影到指定视角。"""
    W, H = img.size
    K = np.array([[W / (2 * np.tan(np.radians(fov / 2))), 0, W_out / 2],
                  [0, H / (2 * np.tan(np.radians(fov / 2))), H_out / 2],
                  [0, 0, 1]], dtype=np.float32)
    R = np.linalg.multi_dot([
        rotation_matrix(pitch, axis="x"),
        rotation_matrix(yaw,   axis="y"),
    ])
    R_h = np.array([[1, 0, 0, 0],
                    [0, -1, 0, 0],
                    [0, 0, -1, 0]], dtype=np.float32)
    P = K @ R_h @ np.vstack([R, [0, 0, 0]])
    out = np.full((H_out, W_out, 3), 255, dtype=np.uint8)
    xyz_cam = []
    for v in range(H_out):
        for u in range(W_out):
            x_c = (u - W_out / 2) / (W_out / 2)
            y_c = (v - H_out / 2) / (H_out / 2)
            ray_local = np.linalg.inv(K) @ np.array([x_c * W_out / 2, y_c * H_out / 2, 1.0])
            ray_global = R @ ray_local
            if ray_global[2] <= 1e-6:
                continue
            lat = np.arcsin(ray_global[1] / np.linalg.norm(ray_global))
            lon = np.arctan2(ray_global[0], ray_global[2])
            px = int((lon / (2 * np.pi) + 0.5) * W) % W
            py = int((0.5 - lat / np.pi) * H)
            px = np.clip(px, 0, W - 1)
            py = np.clip(py, 0, H - 1)
            out[v, u] = img.getpixel((px, py))
    return Image.fromarray(out)

def rotation_matrix(angle_deg, axis="y"):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)
    return np.eye(3)

VIEWS = [
    {"name": "F", "fov": 90, "yaw":   0, "pitch":  0},
    {"name": "B", "fov": 90, "yaw": 180, "pitch":  0},
    {"name": "L", "fov": 90, "yaw": -90, "pitch":  0},
    {"name": "R", "fov": 90, "yaw":  90, "pitch":  0},
    {"name": "U", "fov": 90, "yaw":   0, "pitch": -90},
    {"name": "D", "fov": 90, "yaw":   0, "pitch":  90},
]

VIEW_WEIGHTS = {
    "F": 2.0, "B": 2.0,
    "L": 1.5, "R": 1.5,
    "U": 0.3, "D": 0.3,
}

# ====== 推理 ======
@torch.no_grad()
def process_single(img_path, model, processor, device):
    img = Image.open(img_path).convert("RGB")
    W_img, H_img = img.size

    OUT_SZ = 512  # input resolution for each view

    fused = np.zeros((OUT_SZ, OUT_SZ), dtype=np.float32)
    total_w = 0.0
    for v in VIEWS:
        v_img = equirectangular_to_perspective(img, **({k: v[k] for k in ["fov", "yaw", "pitch"]}), W_out=OUT_SZ, H_out=OUT_SZ)
        inputs = processor(images=[v_img], return_tensors="pt").to(device)
        out = model(**inputs)
        logits = out.logits  # (B, C, H, W) — SegFormer outputs H=W=128
        seg_flat = torch.argmax(logits[0], dim=0)  # (H, W)
        # Upsample to OUT_SZ before fusing
        seg_up = torch.nn.functional.interpolate(
            seg_flat.unsqueeze(0).unsqueeze(0).float(),
            size=(OUT_SZ, OUT_SZ), mode="nearest"
        )[0, 0].cpu().numpy()  # (OUT_SZ, OUT_SZ)
        w = VIEW_WEIGHTS[v["name"]]
        for idx in np.unique(seg_up):
            mask = (seg_up == idx)
            fused[mask] = idx
        total_w += w

    # 全景分割结果resize回原始尺寸
    seg_full = Image.fromarray(fused.astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)

    # 指标计算
    pixels = np.array(seg_full)
    total = pixels.size
    metrics = {}
    for k in CITY_KEYS:
        count = sum(np.sum(pixels == v) for v, n in CITY_CLASSES.items() if n[1] == k)
        metrics[k] = float(count) / total * 100

    # 可视化
    vis = Image.new("RGB", (W_img * 2 + 10, H_img))
    vis.paste(Image.fromarray(np.array(img).astype(np.uint8)), (0, 0))
    overlay = np.array(img).copy().astype(np.float32)
    for name, rgb in COLOR_MAP.items():
        color = np.array(rgb, dtype=np.float32)
        for cls_id, (cn, ct) in CITY_CLASSES.items():
            if ct != name:
                continue
            mask = np.all(np.array(seg_full) == cls_id, axis=-1) if len(np.array(seg_full).shape) > 2 else np.array(seg_full) == cls_id
            alpha = 0.35
            overlay[mask] = overlay[mask] * (1 - alpha) + color * alpha
    vis.paste(Image.fromarray(overlay.astype(np.uint8)), (W_img + 10, 0))

    fname = img_path.stem
    out_viz = OUT_DIR / "viz" / f"{fname}_viz.png"
    out_raw = OUT_DIR / "viz" / f"{fname}_raw.png"
    seg_full.save(out_raw)
    vis.save(out_viz)

    row = [metrics[k] for k in CITY_KEYS] + [
        img_path.name, round(np.median(metrics["sky"]), 2),
        round(metrics["building"] + metrics["road"] + metrics["green"] + metrics["sky"], 2),
        round(metrics["road"] / (metrics["green"] + 0.1), 2),
        round(metrics["building"] / (metrics["green"] + 0.1), 2),
    ]
    return fname, row, seg_full

# ====== 检查点 ======
def load_checkpoint():
    if CKPT_FILE.exists():
        with open(CKPT_FILE) as f:
            return json.load(f)
    return {"done": [], "results": []}

def save_checkpoint(done, results):
    with open(CKPT_FILE, "w") as f:
        json.dump({"done": done, "results": results}, f, ensure_ascii=False)

# ====== 日志 ======
def log(msg):
    ts = time.strftime("%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(OUT_DIR / "inference.log", "a") as f:
        f.write(line + "\n")

# ====== 主循环 ======
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "viz").mkdir(exist_ok=True)
    log("=" * 50)
    log("v6 推理启动 (from_pretrained 正确加载)")

    log(f"数据目录: {DATA_DIR}")
    log(f"模型目录: {MODEL_DIR}")

    # 加载模型 (正确方式)
    model, processor, device = load_model()
    log(f"模型加载完成")

    # 收集图片
    all_jpg = sorted(DATA_DIR.rglob("*.jpg"))
    all_png = sorted(DATA_DIR.rglob("*.png"))
    all_imgs = all_jpg + all_png
    log(f"找到 {len(all_imgs)} 张图片 (jpg:{len(all_jpg)}, png:{len(all_png)})")

    # 恢复检查点
    ckpt = load_checkpoint()
    done_ids = set(ckpt["done"])
    results = ckpt["results"]
    remaining = [p for p in all_imgs if p.stem not in done_ids]
    log(f"已完成: {len(done_ids)}, 剩余: {len(remaining)}, 总计: {len(all_imgs)}")

    # CSV头
    if not OUT_CSV.exists():
        header = CITY_KEYS + ["filename", "median_sky", "built_up", "road_green_ratio", "building_green_ratio"]
        with open(OUT_CSV, "w") as f:
            f.write(",".join(map(str, header)) + "\n")

    # 逐张处理
    for i, img_path in enumerate(remaining):
        try:
            fname, row, _ = process_single(img_path, model, processor, device)
            with open(OUT_CSV, "a") as f:
                f.write(",".join(map(str, row)) + "\n")
            done_ids.add(fname)
            results.append({"fname": fname, "metrics": row})
            if (i + 1) % 5 == 0:
                save_checkpoint(list(done_ids), results)
                log(f"进度: {i+1}/{len(remaining)} ({100*(i+1)/len(remaining):.1f}%) - {fname}")
        except Exception as e:
            log(f"ERROR {img_path.name}: {e}")
            traceback.print_exc()

    save_checkpoint(list(done_ids), results)
    log(f"全部完成！共 {len(done_ids)} 张")

if __name__ == "__main__":
    main()
