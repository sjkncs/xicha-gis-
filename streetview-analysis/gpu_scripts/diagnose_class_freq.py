#!/usr/bin/env python3
"""远端诊断脚本：统计 SegFormer 实际预测的类别 id 分布（top-30）"""
import os, sys, json, csv, math, time
from pathlib import Path
import numpy as np
from PIL import Image

# Try multiple model paths
MODEL_CANDIDATES = [
    "/root/gis_project/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default",
    "/root/gis_project/models/nvidia/segformer-b3-finetuned-ade-512-512",
    "/root/gis_project/models",
]
MODEL_LOCAL = None
import subprocess
for mp in MODEL_CANDIDATES:
    r = subprocess.run(f"ls {mp}/config.json 2>/dev/null && echo EXISTS", shell=True, capture_output=True, text=True)
    if "EXISTS" in r.stdout:
        MODEL_LOCAL = mp
        print(f"Found model at: {mp}")
        break

if MODEL_LOCAL is None:
    r = subprocess.run("find /root/gis_project/models -name 'config.json' 2>/dev/null | head -10", shell=True, capture_output=True, text=True)
    print(f"No known model path. config.json search:\n{r.stdout}")
    sys.exit(1)

from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation

def equirectangular_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    w_img, h_img = equirect.size
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    yr = math.radians(yaw)
    pr = math.radians(pitch)
    fhr = math.radians(fov_h)
    fvr = math.radians(fov_v)
    fx = (out_w / 2.0) / math.tan(fhr / 2.0)
    fy = (out_h / 2.0) / math.tan(fvr / 2.0)
    arr = np.array(equirect)
    cp = math.cos(pr)
    sp = math.sin(pr)
    cy = math.cos(yr)
    sy = math.sin(yr)
    for v in range(out_h):
        dv = (v - out_h / 2.0) / fy
        for u in range(out_w):
            du = (u - out_w / 2.0) / fx
            rx = du * cp * cy - dv * sp * sy
            ry = du * sp + dv * cp
            rz = -du * cp * sy + dv * sp * cy + 1.0
            rlen = math.sqrt(rx*rx + ry*ry + rz*rz)
            if rz == 0:
                continue
            theta = math.acos(rz / rlen)
            phi = math.atan2(ry, rx)
            px = int((phi / (2*math.pi) + 0.5) * w_img) % w_img
            py = int((theta / math.pi) * h_img)
            if 0 <= py < h_img:
                output[v, u] = arr[py, px]
    return Image.fromarray(output)

DATA_DIR = Path("/root/gis_project/data/baidu_streetview")
DEVICE = "cpu"

print("Loading model...")
processor = SegformerImageProcessor.from_pretrained(MODEL_LOCAL)
model = SegformerForSemanticSegmentation.from_pretrained(MODEL_LOCAL)
model = model.to(DEVICE)
model.eval()
print("Model loaded.")

all_jpg = sorted(list(DATA_DIR.glob("*.jpg")) + list(DATA_DIR.glob("*.JPG")))[:10]
print(f"Using {len(all_jpg)} images for diagnosis")

class_counts = {}
yaws = [-150, -90, -30, 30, 90, 150]

for img_path in all_jpg:
    img = Image.open(img_path).convert("RGB")
    views = [equirectangular_to_perspective(img, yaw, 0, 60, 50, 512, 512) for yaw in yaws]

    import torch
    with torch.no_grad():
        batch = views[:4]
        inputs = processor(images=batch, return_tensors="pt")
        inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
        outputs = model(**inputs)
        logits = outputs.logits
        logits = torch.nn.functional.interpolate(logits, size=(512, 512), mode="bilinear", align_corners=False)
        preds = logits.argmax(dim=1).cpu().numpy()

    for pred in preds:
        for cid in pred.flatten():
            class_counts[cid] = class_counts.get(cid, 0) + 1

sorted_classes = sorted(class_counts.items(), key=lambda x: -x[1])
total = sum(class_counts.values())

print("\nTop-30 predicted class IDs (from 10 images, 6 views each):")
print(f"{'Rank':>4}  {'ClassID':>8}  {'Count':>8}  {'Pct':>6}  {'Name':<30}")
print("-" * 65)
for rank, (cid, cnt) in enumerate(sorted_classes[:30], 1):
    pct = cnt / total * 100
    name = model.config.id2label.get(str(cid), "???")
    print(f"{rank:>4}  {cid:>8}  {cnt:>8}  {pct:>5.1f}%  {name:<30}")
