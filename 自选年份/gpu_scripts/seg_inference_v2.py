#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU全景语义分割推理 - SegFormer B3 (ADE20K finetuned)"""
import os, sys, json, time, csv, math
from pathlib import Path

import torch
import numpy as np
from PIL import Image
import cv2

from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

# ========== 配置 ==========
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "nvidia/segformer-b3-finetuned-ade-512-512"
DATA_DIR = Path("/root/gis_project/data/baidu_streetview")
OUT_DIR = Path("/root/gis_project/outputs/segmentation")
MODEL_CACHE = Path("/root/gis_project/models")
CHECKPOINT_FILE = OUT_DIR / "checkpoint_seg.json"
VIZ_DIR = OUT_DIR / "viz"
LOG_FILE = Path("/root/gis_project/logs/seg_inference.log")

OUT_DIR.mkdir(parents=True, exist_ok=True)
VIZ_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

os.environ["HF_HOME"] = str(MODEL_CACHE)
os.environ["TRANSFORMERS_CACHE"] = str(MODEL_CACHE)

# ADE20K 分类 -> 城市语义 (150类ADE20K的子集)
CITY_CLASSES = {
    "building": list(range(0, 35)),     # 0-34: 建筑
    "road": list(range(200, 215)),      # 200-214: 道路/地面
    "sidewalk": [216, 217],
    "green": list(range(120, 160)),    # 120-159: 植被
    "sky": [182, 183, 184, 185, 186, 187, 188, 189, 190, 191],
    "vehicle": [193, 194, 195, 196, 197, 198, 199],
    "person": [12, 13, 14],
    "water": [180, 181],
    "wall": list(range(60, 100)),
    "fence": [101, 102],
    "pole": [163, 164, 165, 166, 167],
}

COLOR_MAP = {
    0: (180, 50, 50),    # wall
    1: (180, 50, 50),    # wall
    2: (180, 50, 50),    # wall
    3: (180, 50, 50),    # building
    4: (180, 50, 50),    # building
    5: (180, 50, 50),    # building
    120: (0, 200, 0),    # tree
    121: (0, 180, 0),    # tree
    122: (0, 160, 0),    # plant
    150: (0, 140, 0),    # grass
    200: (180, 180, 180), # road
    201: (180, 180, 180), # road
    210: (160, 160, 160), # sidewalk
    193: (255, 100, 0),   # car
    194: (255, 100, 0),   # car
    12: (0, 0, 255),     # person
    182: (135, 206, 235), # sky
    183: (135, 206, 235), # sky
    184: (135, 206, 250), # sky
    180: (0, 100, 255),  # water
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done": [], "results": []}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_model():
    log(f"加载模型: {MODEL_NAME} on {DEVICE}")
    t0 = time.time()

    processor = SegformerImageProcessor.from_pretrained(
        MODEL_NAME, cache_dir=MODEL_CACHE, local_files_only=False
    )
    model = SegformerForSemanticSegmentation.from_pretrained(
        MODEL_NAME, cache_dir=MODEL_CACHE, local_files_only=False
    )
    model = model.to(DEVICE)
    model.eval()

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
    log(f"模型加载完成: {time.time()-t0:.1f}s | GPU: {gpu_name}")
    return processor, model


def equirectangular_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    """等距矩形全景图 -> 指定角度的透视视图"""
    w_img, h_img = equirect.size
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)

    yaw_rad, pitch_rad = math.radians(yaw), math.radians(pitch)
    fov_h_rad, fov_v_rad = math.radians(fov_h), math.radians(fov_v)
    fx = (out_w / 2.0) / math.tan(fov_h_rad / 2.0)
    fy = (out_h / 2.0) / math.tan(fov_v_rad / 2.0)

    img_arr = np.array(equirect)
    cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)
    cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)

    for v in range(out_h):
        dv = (v - out_h / 2.0) / fy
        for u in range(out_w):
            du = (u - out_w / 2.0) / fx
            rx = du * cp * cy - dv * sp * sy
            ry = du * sp + dv * cp
            rz = -du * cp * sy + dv * sp * cy + 1.0
            r = math.sqrt(rx*rx + ry*ry + rz*rz)
            if rz == 0:
                continue
            theta = math.acos(rz / r)
            phi = math.atan2(ry, rx)
            px = int((phi / (2*math.pi) + 0.5) * w_img) % w_img
            py = int((theta / math.pi) * h_img)
            if 0 <= py < h_img:
                output[v, u] = img_arr[py, px]

    return Image.fromarray(output)


def process_single(img_path, processor, model):
    """处理一张全景图"""
    try:
        img = Image.open(img_path).convert("RGB")
        W, H = img.size

        # 全景投影: 水平方向每60度切一块（6个视角）
        views = []
        yaws = [-150, -90, -30, 30, 90, 150]
        for yaw in yaws:
            view = equirectangular_to_perspective(img, yaw, 0, 60, 50, 512, 512)
            views.append(view)

        # 融合权重（中心视角权重更高）
        weights = [0.08, 0.17, 0.25, 0.25, 0.17, 0.08]

        # GPU批量推理
        seg_maps = []
        batch_size = 4
        with torch.no_grad():
            for i in range(0, len(views), batch_size):
                batch = views[i:i+batch_size]
                inputs = processor(images=batch, return_tensors="pt")
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                outputs = model(**inputs)
                logits = outputs.logits  # (B, 150, H/4, W/4)
                logits = torch.nn.functional.interpolate(
                    logits, size=(views[0].size[::-1]), mode="bilinear", align_corners=False
                )
                preds = logits.argmax(dim=1).cpu().numpy()
                seg_maps.extend(preds)

        # 加权融合多视角结果
        fusion_h, fusion_w = seg_maps[0].shape
        class_counts = np.zeros((fusion_h, fusion_w, 150), dtype=np.float32)
        for seg_map, w in zip(seg_maps, weights):
            for cls_id in range(150):
                class_counts[:, :, cls_id] += (seg_map == cls_id).astype(np.float32) * w
        combined = class_counts.argmax(axis=2).astype(np.uint8)

        metrics = compute_metrics(combined)
        metrics["pano_name"] = img_path.name
        metrics["pano_path"] = str(img_path)
        metrics["num_views"] = len(views)
        return metrics, combined

    except Exception as e:
        log(f"  处理失败 {img_path.name}: {e}")
        import traceback; traceback.print_exc()
        return None, None


def compute_metrics(pred):
    """基于ADE20K分割计算城市形态指标"""
    total = pred.size
    if total == 0:
        return {}

    m = {}
    for cls_name, cls_ids in CITY_CLASSES.items():
        if isinstance(cls_ids, range):
            cls_ids = list(cls_ids)
        count = np.isin(pred, cls_ids).sum()
        m[f"pct_{cls_name}"] = round(count / total * 100, 2)

    b = m.get("pct_building", 0)
    r = m.get("pct_road", 0)
    g = m.get("pct_green", 0)
    s = m.get("pct_sky", 0)

    m["openness"] = round((s + g + r) / max(b, 1) * 10, 2)
    m["building_density"] = round(b / 10, 2)
    m["canyon_effect"] = round(min(b / max(s + 1, 1) * 5, 10), 2)
    m["walkability"] = round((g * 0.3 + r * 0.4 + s * 0.2 + (100-b) * 0.1) / 100 * 10, 2)

    return m


def save_vis(pred, name, viz_dir):
    """保存分割可视化"""
    try:
        h, w = pred.shape
        vis = np.zeros((h, w, 3), dtype=np.uint8)
        for cls_id, color in COLOR_MAP.items():
            mask = pred == cls_id
            if mask.any():
                vis[mask] = color
        # 背景用灰色
        bg_mask = (vis.sum(axis=2) == 0)
        vis[bg_mask] = (80, 80, 80)
        out_path = viz_dir / f"{name}.png"
        cv2.imwrite(str(out_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    except Exception as e:
        log(f"  可视化失败: {e}")


def append_csv(metrics, csv_path):
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metrics.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)


def main():
    log("=" * 60)
    log("GPU全景图语义分割推理 (SegFormer B3 ADE20K)")
    log(f"设备: {DEVICE} | 模型: {MODEL_NAME}")
    log(f"数据: {DATA_DIR}")
    log(f"输出: {OUT_DIR}")
    log("=" * 60)

    processor, model = load_model()

    jpg_files = sorted(DATA_DIR.glob("*.jpg")) + sorted(DATA_DIR.glob("*.JPG"))
    log(f"找到 {len(jpg_files)} 张全景图")

    if not jpg_files:
        log("ERROR: 没有找到图片!")
        return

    ckpt = load_checkpoint()
    done_names = set(ckpt["done"])
    results = ckpt["results"]

    remaining = [f for f in jpg_files if f.name not in done_names]
    log(f"待处理: {len(remaining)}/{len(jpg_files)}")

    csv_path = OUT_DIR / "seg_results.csv"

    t_start = time.time()
    for i, img_path in enumerate(remaining):
        t_img = time.time()
        log(f"[{i+1}/{len(remaining)}] {img_path.name}...", end=" ", flush=True)

        metrics, pred = process_single(img_path, processor, model)

        if metrics:
            elapsed = time.time() - t_img
            metrics["process_time_s"] = round(elapsed, 2)
            results.append(metrics)
            done_names.add(img_path.name)

            append_csv(metrics, csv_path)
            save_vis(pred, img_path.stem, VIZ_DIR)
            save_checkpoint({"done": list(done_names), "results": results[-100:]})

            log(f"OK {elapsed:.1f}s | "
                 f"建:{metrics.get('pct_building','?')}% "
                 f"路:{metrics.get('pct_road','?')}% "
                 f"绿:{metrics.get('pct_green','?')}% "
                 f"天:{metrics.get('pct_sky','?')}% | "
                 f"开阔:{metrics.get('openness','?')}")

        if (i + 1) % 20 == 0:
            elapsed_total = time.time() - t_start
            avg = elapsed_total / (i + 1)
            eta = avg * len(remaining)
            log(f"  进度: {i+1}/{len(remaining)} "
                 f"| 已用: {elapsed_total/60:.1f}min "
                 f"| 剩余: {eta/60:.1f}min "
                 f"| GPU显存: {torch.cuda.memory_allocated()/1024**3:.2f}GB")

    total = time.time() - t_start
    log(f"===== 全部完成! {len(results)}张 耗时:{total/60:.1f}min =====")


if __name__ == "__main__":
    main()
