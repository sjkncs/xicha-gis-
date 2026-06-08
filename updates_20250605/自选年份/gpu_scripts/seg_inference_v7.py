#!/usr/bin/env python3
"""seg_inference_v7.py - Fixed rotation matrix + vote fusion."""
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
    0: ("road",      "road"),
    1: ("sidewalk",  "road"),
    2: ("building",  "building"),
    3: ("wall",      "building"),
    5: ("fence",     "other"),
    6: ("pole",      "other"),
    7: ("traffic_light", "other"),
    8: ("traffic_sign",  "other"),
    9: ("vegetation", "green"),
    10: ("terrain",   "green"),
    11: ("sky",       "sky"),
    12: ("person",    "person"),
    13: ("rider",     "person"),
    14: ("car",       "car"),
    15: ("truck",     "car"),
    16: ("bus",       "car"),
    17: ("train",     "car"),
    18: ("motorcycle","car"),
    19: ("bicycle",   "car"),
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

# ====== 等距矩形投影 ======
def rot_y(a):
    """绕Y轴旋转，弧度。camera forward=-Z convention."""
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, -s],
                    [0, 1, 0],
                    [s, 0, c]], dtype=np.float32)

def rot_x(a):
    """绕X轴旋转，弧度。"""
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0],
                    [0, c, s],
                    [0, -s, c]], dtype=np.float32)

def equirectangular_to_perspective(img, yaw_deg, pitch_deg, W_out=512, H_out=512):
    """等距矩形 -> 透视视角。
    camera convention: forward=-Z, right=+X, up=+Y
    yaw=0 -> camera looks toward -Z (equirect front)
    """
    W, H = img.size
    arr = np.array(img)
    fov = 90.0
    f = (W_out / 2) / np.tan(np.radians(fov / 2))

    # Camera intrinsics
    K = np.array([[f, 0, W_out/2],
                  [0, f, H_out/2],
                  [0, 0, 1]], dtype=np.float32)
    K_inv = np.linalg.inv(K)

    # Rotation: pitch then yaw
    R = rot_y(np.radians(yaw_deg)) @ rot_x(np.radians(pitch_deg))

    us = np.arange(W_out, dtype=np.float32)
    vs = np.arange(H_out, dtype=np.float32)
    uu, vv = np.meshgrid(us, vs)

    # Camera rays pointing at z=-1 (forward hemisphere)
    rays_cam = np.stack([(uu-W_out/2)/f, (vv-H_out/2)/f, -np.ones_like(uu)], axis=-1)

    # Transform to world space: negate to get forward-pointing rays
    # Then rotate by yaw (Y-axis) and pitch (X-axis)
    rays_world = rays_cam @ R.T  # (H, W, 3) — z<0 means toward front

    # Filter: keep rays with z<0 (front hemisphere)
    valid = rays_world[..., 2] < 0

    # lon = atan2(x, -z) gives 0 at front, ±π at back
    # lat = asin(y / ||r||) gives π/2 at top, -π/2 at bottom
    x, y, z = rays_world[..., 0], rays_world[..., 1], rays_world[..., 2]
    norm = np.sqrt(x**2 + y**2 + z**2) + 1e-8
    lon = np.arctan2(x, -z)
    lat = np.arcsin(np.clip(y / norm, -1, 1))

    # Map to equirectangular pixel coords
    # lon=0→front(equirect center), lon=±π→back(equirect edges)
    # lat=π/2→top, lat=-π/2→bottom
    px_float = ((lon / (2 * np.pi)) + 0.5) * W
    py_float = ((np.pi/2 - lat) / np.pi) * H

    # Build output
    out = np.full((H_out, W_out, 3), 255, dtype=np.uint8)
    px_f = px_float[valid]
    py_f = py_float[valid]
    px_i = np.clip(px_f, 0, W - 1).astype(np.int32)
    py_i = np.clip(py_f, 0, H - 1).astype(np.int32)
    out[valid] = arr[py_i, px_i]
    return Image.fromarray(out)

# 4个水平视角
VIEWS = [
    {"name": "F", "yaw":   0, "pitch": 0},
    {"name": "R", "yaw":  90, "pitch": 0},
    {"name": "B", "yaw": 180, "pitch": 0},
    {"name": "L", "yaw": -90, "pitch": 0},
]

# ====== 推理 ======
@torch.no_grad()
def process_single(img_path, model, processor, device):
    img = Image.open(img_path).convert("RGB")
    W_img, H_img = img.size
    OUT_SZ = 512

    # 每个视角的分割图累积
    vote_maps = {}  # class_id -> accumulator

    for v in VIEWS:
        v_img = equirectangular_to_perspective(img, yaw_deg=v["yaw"], pitch_deg=v["pitch"], W_out=OUT_SZ, H_out=OUT_SZ)
        inputs = processor(images=[v_img], return_tensors="pt").to(device)
        out = model(**inputs)
        logits = out.logits  # (1, 150, H_seg, W_seg)
        H_seg, W_seg = logits.shape[2], logits.shape[3]

        # Upsample to OUT_SZ
        seg_up = torch.nn.functional.interpolate(
            logits.float(), size=(OUT_SZ, OUT_SZ), mode="nearest"
        )[0, 0].cpu().numpy()  # (OUT_SZ, OUT_SZ)

        # Vote accumulation
        for cls_id in np.unique(seg_up):
            mask = (seg_up == cls_id).astype(np.float32)
            vote_maps[int(cls_id)] = vote_maps.get(int(cls_id), np.zeros((OUT_SZ, OUT_SZ), dtype=np.float32)) + mask

    # 每个像素取最多投票的类
    seg_fused = np.full((OUT_SZ, OUT_SZ), 0, dtype=np.int32)
    seg_votes = np.zeros((OUT_SZ, OUT_SZ), dtype=np.float32)
    for cls_id, accum in vote_maps.items():
        mask = accum > seg_votes
        seg_fused[mask] = cls_id
        seg_votes[mask] = accum[mask]

    # Resize to original
    seg_full = Image.fromarray(seg_fused.astype(np.uint8)).resize((W_img, H_img), Image.NEAREST)
    seg_np = np.array(seg_full)

    # Metrics
    total = seg_np.size
    metrics = {}
    for k in CITY_KEYS:
        count = sum(np.sum(seg_np == v) for v, n in CITY_CLASSES.items() if n[1] == k)
        metrics[k] = float(count) / total * 100

    # 可视化
    vis = Image.new("RGB", (W_img * 2 + 10, H_img))
    vis.paste(Image.open(img_path).convert("RGB"), (0, 0))
    overlay = np.array(img).copy().astype(np.float32)
    for name, rgb in COLOR_MAP.items():
        color = np.array(rgb, dtype=np.float32)
        for cls_id, (cn, ct) in CITY_CLASSES.items():
            if ct != name:
                continue
            mask = np.all(seg_np[..., None] == cls_id, axis=-1)
            alpha = 0.4
            overlay[mask] = overlay[mask] * (1 - alpha) + color * alpha
    vis.paste(Image.fromarray(overlay.astype(np.uint8)), (W_img + 10, 0))

    fname = img_path.stem
    vis.save(OUT_DIR / "viz" / f"{fname}_viz.png")
    Image.fromarray(seg_fused.astype(np.uint8)).save(OUT_DIR / "viz" / f"{fname}_raw.png")

    row = [round(metrics[k], 2) for k in CITY_KEYS] + [
        img_path.name,
        round(metrics["sky"], 2),
        round(metrics["building"] + metrics["road"] + metrics["green"] + metrics["sky"], 2),
        round(metrics["road"] / (metrics["green"] + 0.1), 2),
        round(metrics["building"] / (metrics["green"] + 0.1), 2),
    ]
    return fname, row

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
    log("v7 启动 (修复rotation + vote fusion + 4 views)")

    log(f"数据目录: {DATA_DIR}")
    log(f"模型目录: {MODEL_DIR}")

    model, processor, device = load_model()
    log("模型加载完成")

    all_imgs = sorted(DATA_DIR.rglob("*.jpg")) + sorted(DATA_DIR.rglob("*.png"))
    log(f"找到 {len(all_imgs)} 张图片")

    ckpt = load_checkpoint()
    done_ids = set(ckpt["done"])
    results = ckpt["results"]
    remaining = [p for p in all_imgs if p.stem not in done_ids]
    log(f"已完成: {len(done_ids)}, 剩余: {len(remaining)}, 总计: {len(all_imgs)}")

    if not OUT_CSV.exists():
        header = CITY_KEYS + ["filename", "median_sky", "built_up", "road_green_ratio", "building_green_ratio"]
        with open(OUT_CSV, "w") as f:
            f.write(",".join(map(str, header)) + "\n")

    for i, img_path in enumerate(remaining):
        try:
            fname, row = process_single(img_path, model, processor, device)
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
