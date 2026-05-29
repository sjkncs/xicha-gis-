#!/usr/bin/env python3
"""统计本地街景图片"""
from pathlib import Path

base = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")

images = list(base.rglob("*.jpg")) + list(base.rglob("*.png"))
print(f"总图片数: {len(images)}")

# 按区统计
districts = {}
for img in images:
    parts = img.parts
    for p in parts:
        if p in ["南山区", "宝安区", "龙华区", "福田区", "罗湖区", "龙岗区", "盐田区", "坪山区", "光明区", "大鹏新区"]:
            districts[p] = districts.get(p, 0) + 1

print("\n按区统计:")
for d, c in sorted(districts.items(), key=lambda x: -x[1]):
    print(f"  {d}: {c}张")

# 显示总大小
total_size = sum(f.stat().st_size for f in images if f.exists())
print(f"\n总大小: {total_size/1024/1024/1024:.1f} GB")

# 南山区按街道
print("\n南山区子目录:")
ns_base = base / "南山区"
if ns_base.exists():
    for sub in sorted(ns_base.iterdir()):
        if sub.is_dir():
            imgs = list(sub.rglob("*.jpg")) + list(sub.rglob("*.png"))
            print(f"  {sub.name}: {len(imgs)}张")
