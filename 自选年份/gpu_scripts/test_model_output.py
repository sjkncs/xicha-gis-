#!/usr/bin/env python3
"""Test SegFormer output distribution locally."""
import os, sys, json, numpy as np
from pathlib import Path
import torch
from PIL import Image

SNAP_PATH = r"C:\Users\Administrator\.cache\huggingface\hub\models--nvidia--segformer-b3-finetuned-ade-512-512\snapshots\a820c29fc1e53723079d94ca0e09a14d2657fae6"

from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

processor = AutoImageProcessor.from_pretrained(SNAP_PATH)
model = AutoModelForSemanticSegmentation.from_pretrained(SNAP_PATH)
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Find a test image
img_dir = Path(r"e:\xicha gis 智能定位\自选年份\streetview_analysis\images")
imgs = list(img_dir.rglob("*.jpg"))[:3]

for img_path in imgs:
        with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_test_output.txt", "a") as f:
            f.write(f"\n=== {img_path.name} ===\n")
            img = Image.open(img_path).convert("RGB")
            W, H = img.size
            f.write(f"  Size: {W}x{H}\n")

            inputs = processor(images=[img], return_tensors="pt").to(device)
            with torch.no_grad():
                out = model(**inputs)
            logits = out.logits
            f.write(f"  Logits: {logits.shape}\n")

            pred = torch.argmax(logits[0], dim=0)
            pred_np = pred.cpu().numpy()
            H_out, W_out = pred_np.shape
            f.write(f"  Pred shape: {H_out}x{W_out}\n")

            unique, counts = np.unique(pred_np, return_counts=True)
            order = np.argsort(-counts)
            f.write(f"  Total classes: {len(unique)}, Top classes: {[f'c{unique[order[i]]}({counts[order[i]]})' for i in range(min(10, len(order))) ]}\n")

            CITY_CLASSES = {
                0: ("road", "road"), 1: ("sidewalk", "road"), 2: ("building", "building"),
                3: ("wall", "building"), 5: ("fence", "other"), 6: ("pole", "other"),
                7: ("traffic_light", "other"), 8: ("traffic_sign", "other"),
                9: ("vegetation", "green"), 10: ("terrain", "green"),
                11: ("sky", "sky"), 12: ("person", "person"), 13: ("rider", "person"),
                14: ("car", "car"), 15: ("truck", "car"), 16: ("bus", "car"),
                17: ("train", "car"), 18: ("motorcycle", "car"), 19: ("bicycle", "car"),
            }
            total = pred_np.size
            for k in ["building", "road", "green", "sky", "person", "car", "other"]:
                cnt = sum(counts[np.where(unique == v)[0][0]] for v, n in CITY_CLASSES.items() if n[1] == k and v in unique)
                f.write(f"  {k}: {cnt/total*100:.1f}%\n")
