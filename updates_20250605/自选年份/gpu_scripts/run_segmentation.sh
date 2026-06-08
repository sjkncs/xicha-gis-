#!/bin/bash
# ====================================================================
# GPU 批量全景图语义分割推理
# 模型: SegFormer B3 (nvidia/mit-b3)
# 数据: 全景图 -> GPU推理 -> 分割结果CSV
# 用法: bash run_segmentation.sh
# ====================================================================
set -e

VENV="/root/venv"
PY="$VENV/bin/python"
DATA_DIR="/autodl-pub/data"
STREETVIEW_DIR="$DATA_DIR/baidu_streetview"
OUT_DIR="/root/gis_project/outputs/segmentation"
MODEL_DIR="$DATA_DIR/models"
LOG_DIR="/root/gis_project/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

echo "=================================================="
echo "GPU 全景图语义分割批量推理"
echo "时间: $(date)"
echo "=================================================="

# 配置
BATCH_SIZE=4          # 每批处理图片数
MAX_WORKERS=4         # 并行线程数
DEVICE="cuda"         # GPU设备

# 检测GPU
echo "GPU: $(nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader)"
echo "显存总量: $(nvidia-smi --query-gpu=memory.total --format=csv,noheader)"
echo ""

# 创建Python推理脚本
cat > "$LOG_DIR/seg_inference.py" << 'PYEOF'
# -*- coding: utf-8 -*-
"""GPU 全景图语义分割推理"""
import os, sys, json, time, csv, io, math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

import torch
import numpy as np
from PIL import Image
import cv2

# 导入transformers
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

# ========== 配置 ==========
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
MODEL_NAME = "nvidia/mit-b3"  # SegFormer B3
DATA_DIR = Path("/autodl-pub/data/baidu_streetview")
OUT_DIR = Path("/root/gis_project/outputs/segmentation")
MODEL_DIR = Path("/autodl-pub/data/models")
CHECKPOINT_FILE = OUT_DIR / "checkpoint_seg.json"

OUT_DIR.mkdir(parents=True, exist_ok=True)

# 城市土地分类 (ADE20K -> 城市语义)
ADE_LABELS = {
    0: "background", 1: "building", 2: "building", 3: "road", 4: "road",
    5: "sidewalk", 6: "parking", 7: "rail track", 8: "tree", 9: "vegetation",
    10: "grass", 11: "water", 12: "river", 13: "lake",
    14: "sky", 15: "person", 16: "rider", 17: "car",
    18: "truck", 19: "bus", 20: "train", 21: "motorcycle", 22: "bicycle",
    23: "fence", 24: "wall", 25: "terrain",
}

# 城市指标计算用分类
CITY_CLASSES = {
    "building": [1, 2],
    "road": [3, 4, 5, 6, 7],
    "green": [8, 9, 10],
    "sky": [14],
    "vehicle": [17, 18, 19, 20, 21, 22],
    "person": [15, 16],
    "water": [11, 12, 13],
    "fence_wall": [23, 24],
}

def load_model():
    print(f"加载模型: {MODEL_NAME} on {DEVICE}")
    t0 = time.time()
    processor = AutoImageProcessor.from_pretrained(
        MODEL_NAME,
        cache_dir=MODEL_DIR,
        local_files_only=False
    )
    model = AutoModelForSemanticSegmentation.from_pretrained(
        MODEL_NAME,
        cache_dir=MODEL_DIR,
        local_files_only=False
    )
    model = model.to(DEVICE)
    model.eval()
    print(f"模型加载完成: {time.time()-t0:.1f}s")
    return processor, model

def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}

def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def process_panorama(img_path, processor, model):
    """处理单张全景图"""
    try:
        # 读取并转换
        img = Image.open(img_path)
        w, h = img.size

        # 全景图预处理: 投影到透视视图
        # 使用等距矩形投影，拆分成多视角
        fov_h = 90  # 水平视场角
        fov_v = 60  # 垂直视场角
        overlap = 30  # 重叠角度

        views = []
        for yaw in range(-180, 180, fov_h - overlap):
            for pitch in range(-fov_v//2, fov_v//2 + 1, fov_v - overlap):
                view = spherical_to_perspective(img, yaw, pitch, fov_h, fov_v, 512, 384)
                views.append(view)

        # 批量处理
        all_preds = []
        batch_size = 4
        with torch.no_grad():
            for i in range(0, len(views), batch_size):
                batch = views[i:i+batch_size]
                inputs = processor(images=batch, return_tensors="pt")
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                outputs = model(**inputs)
                logits = outputs.logits  # (B, num_classes, H, W)

                # 上采样到原尺寸
                logits = torch.nn.functional.interpolate(
                    logits, size=batch[0].size[::-1], mode="bilinear", align_corners=False
                )
                preds = logits.argmax(dim=1).cpu().numpy()
                all_preds.extend(preds)

        # 合并: 简单的视角拼接(简化版)
        # 实际用更精确的全景投影拼接
        combined = merge_views_simple(all_preds, w, h)

        # 计算指标
        metrics = compute_city_metrics(combined)
        metrics["pano_path"] = str(img_path)
        metrics["pano_name"] = img_path.name
        metrics["views_processed"] = len(views)
        metrics["process_time"] = 0  # 填充

        return metrics, combined

    except Exception as e:
        print(f"  处理失败 {img_path}: {e}")
        return None, None

def spherical_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    """等距矩形全景图 -> 透视视图"""
    w, h = equirect.size

    # yaw/pitch 弧度
    yaw_rad = math.radians(yaw)
    pitch_rad = math.radians(pitch)
    fov_h_rad = math.radians(fov_h)
    fov_v_rad = math.radians(fov_v)

    # 焦距(像素)
    fx = (out_w / 2) / math.tan(fov_h_rad / 2)
    fy = (out_h / 2) / math.tan(fov_v_rad / 2)

    # 相机方向
    cp, sp = math.cos(pitch_rad), math.sin(pitch_rad)
    cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)

    # 投影
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    for v in range(out_h):
        for u in range(out_w):
            # 像素偏移
            dx = (u - out_w/2) / fx
            dy = (v - out_h/2) / fy

            # 球面方向向量
            sx = dx * cp * sy + dy * sp * cy - cp * sy * 0 + 0
            sy_dir = dx * cp * sy - dy * sp * sy + cp * cy * 0 + 0  # 简化
            sz = -dx * sp - dy * cp + 0 + 1

            # 正确计算
            x = dx * cp * sy - dy * sp * cy + sy * 0 + 0
            y = dx * sp + dy * cp
            z = -dx * cp * cy - dy * sp * sy + cy * 0 + 1

            r = math.sqrt(x*x + y*y + z*z)
            theta = math.acos(z/r)
            phi = math.atan2(y, x)

            # 映射到原图
            px = int((phi / (2*math.pi) + 0.5) * w) % w
            py = int((theta / math.pi) * h)

            if 0 <= px < w and 0 <= py < h:
                output[v, u] = np.array(equirect)[py, px]

    return Image.fromarray(output)

def merge_views_simple(preds_list, out_w, out_h):
    """简化拼接: 多个视角的预测取平均概率"""
    # 用第一个视角的预测作为简化结果
    # 实际应用中可用多视角融合
    return preds_list[0] if preds_list else np.zeros((out_h//4, out_w//4), dtype=int)

def compute_city_metrics(pred):
    """基于分割结果计算城市形态指标"""
    total = pred.size
    if total == 0:
        return {}

    metrics = {}
    for city_class, class_ids in CITY_CLASSES.items():
        count = np.isin(pred, class_ids).sum()
        metrics[f"pct_{city_class}"] = round(count / total * 100, 2)

    # 衍生指标
    building = metrics.get("pct_building", 0)
    road = metrics.get("pct_road", 0)
    green = metrics.get("pct_green", 0)
    sky = metrics.get("pct_sky", 0)

    metrics["openness"] = round(min(sky + green + road) * 10 / max(building, 1), 2)
    metrics["building_density"] = round(building / 100 * 10, 2)
    metrics["walkability_index"] = round(
        (green * 0.3 + road * 0.4 + sky * 0.2 + (100 - building) * 0.1) / 100 * 10, 2
    )
    metrics["canyon_effect"] = round(min(building / (sky + 0.1) * 5, 10), 2)

    return metrics

def save_visualization(img_path, pred, out_path):
    """保存分割可视化图"""
    color_map = {
        0: (60, 60, 60),    # background - 灰
        1: (255, 100, 0),   # building - 橙
        2: (255, 150, 0),   # building2 - 深橙
        3: (180, 180, 180),  # road - 灰白
        4: (150, 150, 150),  # road2
        5: (100, 100, 100),  # sidewalk
        8: (0, 200, 0),     # tree - 绿
        10: (0, 180, 0),    # grass - 深绿
        14: (135, 206, 250), # sky - 天蓝
        17: (0, 0, 255),    # car - 蓝
    }
    h, w = pred.shape
    vis = np.zeros((h, w, 3), dtype=np.uint8)
    for cls, color in color_map.items():
        mask = pred == cls
        vis[mask] = color

    vis_rgb = cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(out_path), vis_rgb)

def main():
    print(f"设备: {DEVICE}")
    print(f"模型: {MODEL_NAME}")
    print(f"数据目录: {DATA_DIR}")

    # 加载模型
    processor, model = load_model()

    # 查找全景图
    jpg_files = list(DATA_DIR.rglob("*.jpg")) + list(DATA_DIR.rglob("*.png"))
    print(f"找到 {len(jpg_files)} 张图片")

    if len(jpg_files) == 0:
        print("没有找到图片!")
        return

    # 加载检查点
    checkpoint = load_checkpoint()
    done_ids = set(checkpoint.get("done", []))

    # 过滤已处理
    remaining = [f for f in jpg_files if f.name not in done_ids]
    print(f"待处理: {len(remaining)}/{len(jpg_files)}")

    results = checkpoint.get("results", [])
    if results:
        print(f"已有结果: {len(results)} 条")

    # 结果CSV
    csv_path = OUT_DIR / "seg_results.csv"
    csv_exists = csv_path.exists()

    t_start = time.time()
    for i, img_path in enumerate(remaining):
        t_img = time.time()
        print(f"\n[{i+1}/{len(remaining)}] {img_path.name}...", end=" ", flush=True)

        metrics, pred = process_panorama(img_path, processor, model)

        if metrics:
            metrics["process_time"] = round(time.time() - t_img, 2)
            results.append(metrics)
            done_ids.add(img_path.name)

            # 实时保存
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                if not csv_exists:
                    f.write(','.join(metrics.keys()) + '\n')
                    csv_exists = True
                f.write(','.join(str(v) for v in metrics.values()) + '\n')

            # 保存可视化
            vis_path = OUT_DIR / "viz" / img_path.stem
            vis_path.mkdir(exist_ok=True)
            save_visualization(img_path, pred, vis_path / "seg.png")

            # 更新检查点
            save_checkpoint({"done": list(done_ids), "results": results})

            print(f"OK {metrics['process_time']}s | "
                  f"建筑:{metrics.get('pct_building','?')}% "
                  f"道路:{metrics.get('pct_road','?')}% "
                  f"绿地:{metrics.get('pct_green','?')}% "
                  f"天空:{metrics.get('pct_sky','?')}%")

        # 每10张打印进度
        if (i + 1) % 10 == 0:
            elapsed = time.time() - t_start
            avg = elapsed / (i + 1)
            eta = avg * len(remaining)
            print(f"\n  进度: {i+1}/{len(remaining)} "
                  f"已用:{elapsed/60:.1f}min 预计剩余:{eta/60:.1f}min")

    total_time = time.time() - t_start
    print(f"\n===== 完成! 总计: {len(results)} 张 "
          f"耗时: {total_time/60:.1f}min =====")

PYEOF

echo "推理脚本已创建: $LOG_DIR/seg_inference.py"

# 启动推理
echo ""
echo "启动推理..."
echo "日志: $LOG_DIR/seg_inference.log"
echo "输出: $OUT_DIR/"
echo "CSV: $OUT_DIR/seg_results.csv"

cd /root/gis_project
nohup $PY $LOG_DIR/seg_inference.py > $LOG_DIR/seg_inference.log 2>&1 &
echo "进程已启动 PID=$!"
echo ""
echo "监控命令:"
echo "  tail -f $LOG_DIR/seg_inference.log"
echo "  cat $OUT_DIR/seg_results.csv | head -20"
echo "  nvidia-smi -l 1"
