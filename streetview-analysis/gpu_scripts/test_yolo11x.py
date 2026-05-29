#!/usr/bin/env python3
"""最小化测试：只加载yolo11x，测单张图"""
import os, sys, time
os.environ["YOLO_VERBOSE"] = "False"

import torch
from ultralytics import YOLO

MODEL = "/root/autodl-tmp/streetview_analysis/yolo_models/yolo11x.pt"
IMG   = "/root/autodl-tmp/streetview_analysis/images"
OUT   = "/root/autodl-tmp/streetview_analysis/yolo_test_results"
os.makedirs(OUT, exist_ok=True)

print("CUDA:", torch.cuda.is_available())
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None")

print("Loading yolo11x...")
t0 = time.time()
model = YOLO(MODEL)
print(f"Model loaded in {time.time()-t0:.1f}s")

# 找第一张图
imgs = [os.path.join(r,f) for r,_,fs in os.walk(IMG) for f in fs if f.endswith('.jpg')]
if not imgs:
    print("No images found!"); sys.exit(1)
test_img = imgs[0]
print(f"Test image: {test_img}")

print("Running prediction...")
t1 = time.time()
results = model.predict(test_img, conf=0.35, verbose=False, device="cuda")
t2 = time.time()
print(f"Prediction done in {t2-t1:.1f}s")
print(f"Boxes: {len(results[0].boxes)}")

for i in range(len(results[0].boxes)):
    cls_id = int(results[0].boxes.cls[i])
    conf = float(results[0].boxes.conf[i])
    print(f"  cls={cls_id} conf={conf:.3f}")

results[0].save(f"{OUT}/test_result.jpg")
print(f"Saved to {OUT}/test_result.jpg")
print("DONE")
