#!/usr/bin/env python3
import json, os, sys
from collections import defaultdict
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

with open(f"{LOCAL_RESULTS}/all_results_fixed.json", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
print(f"Nanshan: {len(nanshan)} images")

# Parse street from image path:
# /root/autodl-tmp/streetview_analysis/images/南山区/{街道}/{社区}/OpenOther-开放其他/{coords}/{file}.jpg
# Or the server heatmap files show:
# 南山区_南头_未知社区_OpenOther-开放其他_坐标_坐标_方向_2022_fcn.jpg

def get_street_from_path(path):
    parts = path.split("/")
    # Expected: ['', 'root', 'autodl-tmp', 'streetview_analysis', 'images', '南山区', '街道', '社区', 'OpenOther-开放其他', 'coords', 'filename.jpg']
    if len(parts) >= 7 and parts[5] == "南山区":
        return parts[6]
    return "未知街道"

def get_coords_from_path(path):
    parts = path.split("/")
    if len(parts) >= 8:
        return parts[7]
    return ""

street_data = defaultdict(lambda: {"imgs": [], "scores": [], "cats": defaultdict(int), "coords": set()})

for r in nanshan:
    street = get_street_from_path(r["image"])
    coords = get_coords_from_path(r["image"])
    street_data[street]["imgs"].append(r["image"].split("/")[-1])
    street_data[street]["scores"].append(r["accessibility_score"])
    street_data[street]["coords"].add(coords)
    for cat, cnt in r["categories"].items():
        street_data[street]["cats"][cat] += cnt

print("\nStreet breakdown (from image paths):")
for street, info in sorted(street_data.items(), key=lambda x: -len(x[1]["scores"])):
    scores = info["scores"]
    mean_s = float(np.mean(scores))
    cats_str = ", ".join([f"{k}({v})" for k,v in sorted(info["cats"].items(), key=lambda x:-x[1])[:5]])
    rating = "正常" if mean_s < 15 else "一般" if mean_s < 25 else "较困难" if mean_s < 40 else "困难"
    print(f"\n  {street}: n={len(scores)}, coords={len(info['coords'])}, mean={mean_s:.1f}, max={max(scores):.0f} [{rating}]")
    print(f"    cats: {cats_str}")
