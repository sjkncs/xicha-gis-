# -*- coding: utf-8 -*-
import csv
from pathlib import Path
from collections import Counter

base = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")

print("=" * 70)
print("全量街景采集完成报告")
print("=" * 70)

# 1. 区级统计
print("\n[1] 区级图像统计")
print("-" * 50)
total_imgs = 0
for d in sorted(base.iterdir()):
    if d.is_dir() and d.suffix == "" and d.name != ".pipeline_cache":
        imgs = list(d.rglob("*.jpg"))
        total_imgs += len(imgs)
        if imgs:
            print(f"  {d.name:10s} -> {len(imgs):3d} 张")

# 排除 manifest.csv 和遗留目录
valid_imgs = []
for d in sorted(base.iterdir()):
    if d.is_dir() and d.name in ["南山区", "宝安区", "光明区", "龙华区"]:
        valid_imgs.extend(list(d.rglob("*.jpg")))

print(f"\n  有效图像总数（仅归档目录）: {len(valid_imgs)} 张")

# 2. 南山区各街道
print("\n[2] 南山区各街道统计")
print("-" * 50)
ns = base / "南山区"
if ns.exists():
    for t in sorted(ns.iterdir()):
        if t.is_dir():
            # 各形态
            forms = Counter()
            for c in t.iterdir():
                if c.is_dir():
                    for uf in c.iterdir():
                        if uf.is_dir():
                            forms[uf.name] += len(list(uf.rglob("*.jpg")))
            imgs = list(t.rglob("*.jpg"))
            print(f"  {t.name} -> {len(imgs):3d} 张  ({len(list(t.iterdir()))} 社区)")
            for uf, cnt in sorted(forms.items()):
                if cnt > 0:
                    print(f"      {uf}: {cnt} 张")

# 3. manifest 统计
print("\n[3] manifest.csv 统计")
print("-" * 50)
manifest = base / "manifest.csv"
if manifest.exists():
    rows = []
    with open(manifest, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    print(f"  总记录数: {len(rows)}")

    dist_cnt = Counter(r.get("district","") for r in rows)
    print(f"\n  各区分布:")
    for k, v in dist_cnt.most_common():
        print(f"    {k:10s}: {v:3d} 张")

    twp_cnt = Counter(r.get("township","") for r in rows)
    print(f"\n  各街道分布:")
    for k, v in twp_cnt.most_common():
        print(f"    {k:10s}: {v:3d} 张")

    form_cnt = Counter(r.get("urban_form","") for r in rows)
    print(f"\n  各城市形态:")
    for k, v in form_cnt.most_common():
        print(f"    {k:15s}: {v:3d} 张")

    # 年份分布
    year_cnt = Counter(r.get("year","") for r in rows)
    print(f"\n  各年份:")
    for k, v in year_cnt.most_common():
        print(f"    {k}: {v} 张")

# 4. 归档层级结构示例
print("\n[4] 南山区归档结构示例（前3个街道）")
print("-" * 50)
if ns.exists():
    shown = 0
    for t in sorted(ns.iterdir()):
        if t.is_dir() and shown < 3:
            print(f"\n  {t.name}/")
            for c in sorted(t.iterdir())[:3]:
                if c.is_dir():
                    print(f"    {c.name}/")
                    for uf in sorted(c.iterdir())[:2]:
                        if uf.is_dir():
                            imgs = list(uf.rglob("*.jpg"))
                            print(f"      {uf.name}/  -> {len(imgs)} 张")
            shown += 1

print("\n" + "=" * 70)
print(f"归档目录: {base}")
print(f"清单文件: {manifest}")
print("=" * 70)
