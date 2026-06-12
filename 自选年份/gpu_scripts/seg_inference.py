#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GPU全景语义分割推理 - SegFormer B3"""
import os, sys, json, time, csv, io, math
from pathlib import Path

import torch
import numpy as np
from PIL import Image
import cv2

from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

# ========== 配置 ==========
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "nvidia/mit-b3"
DATA_DIR = Path("/autodl-pub/data/baidu_streetview")
OUT_DIR = Path("/root/gis_project/outputs/segmentation")
MODEL_DIR = Path("/autodl-pub/data/models")
CHECKPOINT_FILE = OUT_DIR / "checkpoint_seg.json"
VIZ_DIR = OUT_DIR / "viz"
LOG_FILE = Path("/root/gis_project/logs/seg_inference.log")

OUT_DIR.mkdir(parents=True, exist_ok=True)
VIZ_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# ADE20K 分类 -> 城市语义
CITY_CLASSES = {
    "building": [1, 2],
    "road": [3, 4, 5, 6, 7],
    "green": [8, 9, 10],
    "sky": [14],
    "vehicle": [17, 18, 19, 20, 21, 22],
    "person": [15, 16],
    "water": [11, 12, 13],
}

# 可视化颜色 (BGR for cv2)
COLOR_MAP = {
    0: (60, 60, 60),    # background
    1: (0, 100, 255),    # building
    2: (0, 80, 255),     # building
    3: (180, 180, 180),  # road
    4: (150, 150, 150),  # road
    5: (120, 120, 120),  # sidewalk
    8: (0, 200, 0),      # tree
    10: (0, 160, 0),     # grass
    14: (250, 206, 135),  # sky
    17: (255, 0, 0),       # car
}


def log(msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"done": [], "results": []}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def load_model():
    log(f"加载模型: {MODEL_NAME} on {DEVICE}")
    t0 = time.time()
    processor = AutoImageProcessor.from_pretrained(
        MODEL_NAME, cache_dir=MODEL_DIR, local_files_only=False
    )
    model = AutoModelForSemanticSegmentation.from_pretrained(
        MODEL_NAME, cache_dir=MODEL_DIR, local_files_only=False
    )
    model = model.to(DEVICE)
    model.eval()
    log(f"模型加载完成: {time.time()-t0:.1f}s, GPU: {torch.cuda.get_device_name(0)}")
    return processor, model


def equirectangular_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    """等距矩形全景图 -> 指定角度的透视视图"""
    w_img, h_img = equirect.size
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)

    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)
    fov_h_rad = math.radians(fov_h)
    fov_v_rad = math.radians(fov_v)

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

        # 全景投影: 拆成多视角 (水平方向每90度切一块)
        step = 90
        views = []
        for yaw in range(-180, 180, step):
            view = equirectangular_to_perspective(img, yaw, 0, 90, 60, 512, 384)
            views.append(view)

        # GPU批量推理
        seg_maps = []
        batch_size = 4
        with torch.no_grad():
            for i in range(0, len(views), batch_size):
                batch = views[i:i+batch_size]
                inputs = processor(images=batch, return_tensors="pt")
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                outputs = model(**inputs)
                logits = outputs.logits  # (B, C, H, W)
                logits = torch.nn.functional.interpolate(
                    logits, size=batch[0].size[::-1], mode="bilinear", align_corners=False
                )
                preds = logits.argmax(dim=1).cpu().numpy()
                seg_maps.extend(preds)

        # 取第一块视角的分割结果作为代表
        combined = seg_maps[0] if seg_maps else np.zeros((H//4, W//4), dtype=int)
        metrics = compute_metrics(combined)
        metrics["pano_name"] = img_path.name
        metrics["pano_path"] = str(img_path)
        metrics["num_views"] = len(views)
        return metrics, combined

    except Exception as e:
        log(f"  处理失败 {img_path.name}: {e}")
        return None, None


def compute_metrics(pred):
    """基于分割计算城市形态指标"""
    total = pred.size
    if total == 0:
        return {}

    m = {}
    for cls_name, cls_ids in CITY_CLASSES.items():
        count = np.isin(pred, cls_ids).sum()
        m[f"pct_{cls_name}"] = round(count / total * 100, 2)

    b = m.get("pct_building", 0)
    r = m.get("pct_road", 0)
    g = m.get("pct_green", 0)
    s = m.get("pct_sky", 0)

    m["openness"] = round(min(s + g + r) / max(b, 1) * 10, 2)
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
            vis[mask] = color
        out_path = viz_dir / f"{name}.png"
        cv2.imwrite(str(out_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
    except Exception as e:
        log(f"  可视化保存失败: {e}")


def append_csv(metrics, csv_path):
    """追加到CSV"""
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metrics.keys())
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)


def main():
    log("=" * 50)
    log("GPU全景图语义分割推理启动")
    log(f"设备: {DEVICE} | 模型: {MODEL_NAME}")
    log(f"输出: {OUT_DIR}")
    log("=" * 50)

    # 加载模型
    processor, model = load_model()

    # 查找图片
    jpg_files = []
    for ext in ["*.jpg", "*.JPG", "*.jpeg", "*.png", "*.PNG"]:
        jpg_files.extend(DATA_DIR.rglob(ext))
    log(f"找到 {len(jpg_files)} 张图片")

    if not jpg_files:
        log("ERROR: 没有找到图片!")
        return

    # 加载检查点
    ckpt = load_checkpoint()
    done_names = set(ckpt["done"])
    results = ckpt["results"]

    remaining = [f for f in jpg_files if f.name not in done_names]
    log(f"待处理: {len(remaining)}/{len(jpg_files)}")

    csv_path = OUT_DIR / "seg_results.csv"

    t_start = time.time()
    for i, img_path in enumerate(remaining):
        t_img = time.time()
        log(f"[{i+1}/{len(remaining)}] {img_path.name}...", end=" ")
        sys.stdout.flush()

        metrics, pred = process_single(img_path, processor, model)

        if metrics:
            elapsed = time.time() - t_img
            metrics["process_time_s"] = round(elapsed, 1)
            results.append(metrics)
            done_names.add(img_path.name)

            append_csv(metrics, csv_path)
            save_vis(pred, img_path.stem, VIZ_DIR)
            save_checkpoint({"done": list(done_names), "results": results[-100:]})

            log(f"OK {elapsed:.1f}s | "
                 f"建筑:{metrics.get('pct_building','?')}% "
                 f"道路:{metrics.get('pct_road','?')}% "
                 f"绿地:{metrics.get('pct_green','?')}% "
                 f"天空:{metrics.get('pct_sky','?')}% | "
                 f"开阔度:{metrics.get('openness','?')}")

        if (i + 1) % 20 == 0:
            elapsed = time.time() - t_start
            avg = elapsed / (i + 1)
            eta = avg * len(remaining)
            log(f"  进度: {i+1}/{len(remaining)} "
                 f"| 已用: {elapsed/60:.1f}min "
                 f"| 预计剩余: {eta/60:.1f}min "
                 f"| GPU显存: {torch.cuda.memory_allocated()/1024**3:.1f}GB")

    total = time.time() - t_start
    log(f"===== 全部完成! {len(results)}张 耗时:{total/60:.1f}min =====")


if __name__ == "__main__":
    main()
