#!/usr/bin/env python3
"""
v8: Simple direct segmentation of original images.
No projection - just resize each image to 512x512 and segment.
Then aggregate metrics across all images.
"""
import numpy as np
from pathlib import Path
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
import torch

# ADE20K class index -> urban metric category
# Based on ADE20K class definitions
def cls_to_metric(cls_id):
    cid = int(cls_id)
    # Buildings & walls
    if cid in [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]:
        return "building"
    # Roads & sidewalks
    if cid in [1]:
        return "road"
    # Vegetation
    if cid in [22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34]:
        return "green"
    # Sky
    if cid in [40]:
        return "sky"
    # Person
    if cid == 12:
        return "person"
    # Vehicles
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
imgs = sorted(img_dir.rglob("*.jpg"))  # recursive glob
print(f"Found {len(imgs)} images")

# Process all images
METRICS = ["building", "road", "green", "sky", "person", "car", "other"]
agg = {m: 0 for m in METRICS}
total_pixels = 0

results = []
for img_path in imgs:
    img = Image.open(img_path).convert("RGB")
    W, H = img.size

    # Resize to 512x512 (model input size)
    img_512 = img.resize((512, 512), Image.LANCZOS)

    inputs = processor(images=img_512, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits  # (1, 150, H, W)
    print(f"  {img_path.name}: logits={logits.shape}")

    seg = logits.argmax(dim=1)[0].cpu().numpy()  # (H, W)
    total = seg.size

    # Count pixels per category
    cats = {m: 0 for m in METRICS}
    for u in np.unique(seg):
        m = cls_to_metric(int(u))
        c = int(np.sum(seg == u))
        cats[m] += c

    # Print per-image result
    res = {m: cats[m] / total * 100 for m in METRICS}
    print(f"    {res}")
    results.append((img_path.name, res))

    # Aggregate
    for m in METRICS:
        agg[m] += cats[m]
    total_pixels += total

# Overall averages
if total_pixels > 0:
    print(f"\n=== OVERALL AVERAGES (n={len(imgs)}) ===")
    for m in METRICS:
        pct = agg[m] / total_pixels * 100
        print(f"  {m}: {pct:.1f}%")

# Save summary
with open("/root/autodl-tmp/v8_results.txt", "w") as f:
    f.write(f"Total images: {len(imgs)}\n")
    f.write(f"Total pixels: {total_pixels}\n")
    f.write("Per-image results:\n")
    for name, res in results:
        f.write(f"  {name}: {res}\n")
    f.write("\nOverall:\n")
    for m in METRICS:
        pct = agg[m] / total_pixels * 100
        f.write(f"  {m}: {pct:.1f}%\n")

print("\nDone! Results saved to /root/autodl-tmp/v8_results.txt")
