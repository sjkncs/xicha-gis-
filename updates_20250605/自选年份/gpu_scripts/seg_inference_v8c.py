#!/usr/bin/env python3
"""
v8c: Full pipeline - direct segmentation of all images, output CSV + colored viz.
Each image is a 512x512 perspective view.
For each location (lat_lon), average metrics from 4 directions.
"""
import numpy as np
from pathlib import Path
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation
import torch, csv, io

# ADE20K class index -> urban metric
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

# ADE20K -> RGB color for visualization
def ade_to_color(cls_id):
    cid = int(cls_id)
    colors = {
        0: (120,120,120), 1: (128,64,128), 2: (70,70,70), 3: (153,153,153),
        4: (107,142,35), 5: (70,130,180), 6: (220,20,60), 7: (0,0,142),
        8: (0,0,0), 9: (244,35,232), 10: (160,82,45), 11: (255,255,128),
        12: (153,153,153), 13: (0,0,142), 14: (220,20,60), 15: (0,0,0),
        22: (107,142,35), 23: (152,251,152), 24: (70,130,180), 40: (70,130,180),
        49: (220,20,60), 50: (0,0,142),
    }
    return colors.get(cid, (128, 128, 128))

def metric_to_color(metric):
    colors = {
        "building": (70, 70, 70),
        "road": (128, 64, 128),
        "green": (107, 142, 35),
        "sky": (135, 206, 235),
        "person": (220, 20, 60),
        "car": (0, 0, 142),
        "other": (128, 128, 128),
    }
    return colors.get(metric, (128, 128, 128))

METRICS = ["building", "road", "green", "sky", "person", "car", "other"]

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

out_dir = Path("/root/autodl-tmp/outputs/v8c")
out_dir.mkdir(parents=True, exist_ok=True)
viz_dir = out_dir / "viz"
viz_dir.mkdir(exist_ok=True)

results = []  # per-image results
agg_by_loc = {}  # location -> aggregated metrics

for img_path in imgs:
    img = Image.open(img_path).convert("RGB")
    inputs = processor(images=img, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits
    seg = logits.argmax(dim=1)[0].cpu().numpy()  # (H', W')
    total = seg.size

    # Count pixels
    cats = {m: 0 for m in METRICS}
    for u in np.unique(seg):
        m = cls_to_metric(int(u))
        cats[m] += int(np.sum(seg == u))

    # Per-image percentage
    pct = {m: cats[m] / total * 100 for m in METRICS}
    lat_lon = img_path.parent.name  # e.g. "113.884019_22.500940"
    direction = img_path.stem.split("_")[-1]  # e.g. "E"

    results.append({
        "filename": img_path.name,
        "lat_lon": lat_lon,
        "direction": direction,
        "path": str(img_path),
        **{f"px_{m}": cats[m] for m in METRICS},
        **{f"pct_{m}": round(pct[m], 2) for m in METRICS},
    })

    # Aggregate by location
    if lat_lon not in agg_by_loc:
        agg_by_loc[lat_lon] = {m: 0 for m in METRICS}
    for m in METRICS:
        agg_by_loc[lat_lon][m] += cats[m]

    # Generate colored visualization (vectorized)
    H, W = seg.shape
    color_map = np.array([
        metric_to_color(m) for m in [cls_to_metric(i) for i in range(150)]
    ], dtype=np.uint8)
    colored = color_map[seg]  # (H, W, 3) - direct lookup

    # Blend: 60% original, 40% colored
    orig_small = np.array(img.resize((W, H), Image.LANCZOS), dtype=np.float32)
    colored_f = colored.astype(np.float32)
    blended = (0.6 * orig_small + 0.4 * colored_f).clip(0, 255).astype(np.uint8)
    blended_img = Image.fromarray(blended)
    # Save
    out_name = f"{lat_lon}_{direction}_blend.png"
    blended_img.save(str(viz_dir / out_name))

# Write per-image CSV
csv_path = out_dir / "per_image_metrics.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    if results:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
print(f"Wrote per-image CSV: {csv_path}")

# Write per-location CSV
loc_results = []
for lat_lon, cats in sorted(agg_by_loc.items()):
    total = sum(cats.values())
    loc_results.append({
        "lat_lon": lat_lon,
        "n_images": 4,
        **{f"px_{m}": cats[m] for m in METRICS},
        **{f"pct_{m}": round(cats[m]/total*100, 2) for m in METRICS},
    })

loc_csv = out_dir / "per_location_metrics.csv"
with open(loc_csv, "w", newline="", encoding="utf-8") as f:
    if loc_results:
        writer = csv.DictWriter(f, fieldnames=list(loc_results[0].keys()))
        writer.writeheader()
        writer.writerows(loc_results)
print(f"Wrote per-location CSV: {loc_csv}")

# Print overall
total_pixels = sum(sum(cats.values()) for cats in agg_by_loc.values())
overall = {m: sum(cats[m] for cats in agg_by_loc.values()) for m in METRICS}
print(f"\n=== OVERALL (n_locs={len(agg_by_loc)}, n_imgs={len(imgs)}) ===")
for m in METRICS:
    print(f"  {m}: {overall[m]/total_pixels*100:.2f}%")

# Save summary
with open(out_dir / "summary.txt", "w") as f:
    f.write(f"Total locations: {len(agg_by_loc)}\n")
    f.write(f"Total images: {len(imgs)}\n")
    f.write(f"Total pixels: {total_pixels}\n\n")
    for m in METRICS:
        f.write(f"  {m}: {overall[m]/total_pixels*100:.2f}%\n")
print("Done!")
