#!/usr/bin/env python3
"""
v8b: Fix percentage calculation - properly count argmax pixels per category.
"""
import numpy as np
from pathlib import Path
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
import torch

def cls_to_metric(cls_id):
    cid = int(cls_id)
    if cid in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        return "building"
    if cid in [1]:
        return "road"
    if cid in [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34]:
        return "green"
    if cid in [40]:
        return "sky"
    if cid == 12:
        return "person"
    if cid in [13, 14, 15, 16, 17, 18, 19, 20, 21]:
        return "car"
    return "other"

# Load model
snap = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
print("Loading model...")
processor = AutoImageProcessor.from_pretrained(snap, local_files_only=True)
model = AutoModelForSemanticSegmentation.from_pretrained(snap, local_files_only=True)
model = model.to("cuda").eval()
print("Model loaded!")

img_dir = Path("/root/autodl-tmp/streetview_analysis/images")
imgs = sorted(img_dir.rglob("*.jpg"))
print(f"Found {len(imgs)} images")

METRICS = ["building", "road", "green", "sky", "person", "car", "other"]
agg = {m: 0 for m in METRICS}
total_pixels = 0

for img_path in imgs:
    img = Image.open(img_path).convert("RGB")
    inputs = processor(images=img, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits  # (1, 150, H', W')
    # Argmax -> class index per pixel
    seg = logits.argmax(dim=1)[0].cpu().numpy()  # (H', W')
    total = seg.size

    # Count pixels per category using argmax
    cats = {m: 0 for m in METRICS}
    for u in np.unique(seg):
        m = cls_to_metric(int(u))
        cats[m] += int(np.sum(seg == u))

    # Per-image percentage
    pct = {m: cats[m] / total * 100 for m in METRICS}
    print(f"{img_path.name}: b={pct['building']:.1f}% r={pct['road']:.1f}% g={pct['green']:.1f}% sk={pct['sky']:.1f}% c={pct['car']:.1f}%")

    # Aggregate
    for m in METRICS:
        agg[m] += cats[m]
    total_pixels += total

# Overall
print(f"\n=== OVERALL (n={len(imgs)}, total_pixels={total_pixels}) ===")
for m in METRICS:
    pct = agg[m] / total_pixels * 100
    print(f"  {m}: {pct:.2f}%")

# Save
with open("/root/autodl-tmp/v8b_results.txt", "w") as f:
    f.write(f"Total images: {len(imgs)}\nTotal pixels: {total_pixels}\n")
    for m in METRICS:
        f.write(f"  {m}: {agg[m]/total_pixels*100:.2f}%\n")
print("Done!")
