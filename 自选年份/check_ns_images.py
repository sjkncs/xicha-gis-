# -*- coding: utf-8 -*-
"""分析南山区图像元数据，确保路径完整"""
import csv
from pathlib import Path

base = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
manifest = base / "manifest.csv"

rows = []
with open(manifest, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"总记录: {len(rows)}")

# 南山区
ns_rows = [r for r in rows if r.get("district", "").strip() == "南山区"]
print(f"南山区: {len(ns_rows)}")

# 各字段缺失检查
for field in ["district", "township", "community", "urban_form", "road_fclass", "road_name"]:
    missing = sum(1 for r in ns_rows if not r.get(field, "").strip() or r.get(field) == "[]")
    print(f"  {field} 缺失: {missing}/{len(ns_rows)}")

# 各街道统计
from collections import Counter
twp = Counter(r.get("township", "") for r in ns_rows)
print(f"\n各街道:")
for k, v in twp.most_common():
    print(f"  {k}: {v} 张")

# 各社区
neigh = Counter(r.get("community", "") for r in ns_rows)
print(f"\n各社区:")
for k, v in neigh.most_common():
    print(f"  {k}: {v} 张")

# 归档路径示例（南山区前10）
print(f"\n归档路径示例（前10个）:")
for r in ns_rows[:10]:
    p = r.get("archive_path", "")
    # 提取相对路径
    parts = p.replace(str(base) + "\\", "").replace(str(base) + "/", "")
    print(f"  {parts}")

# 生成南山区图像清单 CSV（带完整相对路径）
print(f"\n生成 ns_manifest.csv...")
ns_out = base / "ns_manifest.csv"
fields = ["archive_path", "district", "township", "community", "urban_form",
          "road_fclass", "road_name", "lng", "lat", "heading", "heading_label", "year", "size"]
with open(ns_out, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for r in ns_rows:
        w.writerow({k: r.get(k, "") for k in fields})
print(f"  已保存: {ns_out}")
print(f"  共 {len(ns_rows)} 条记录")

# 验证图像文件存在
print(f"\n验证图像文件存在（前10个）...")
missing = 0
for r in ns_rows[:20]:
    p = Path(r.get("archive_path", ""))
    if p.exists():
        print(f"  OK: {p.name[:30]}")
    else:
        print(f"  MISSING: {p}")
        missing += 1
print(f"  前20个中缺失: {missing}")
