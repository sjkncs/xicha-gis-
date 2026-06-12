"""
分析 n201 的 road_name 字段，提取可能的街道/社区信息
"""
import csv
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = Path(__file__).parent
n201_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n201.csv"

rows = []
with open(n201_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"n201 total: {len(rows)} rows")

# 分析 road_name 字段
road_names = {}
for row in rows:
    rn = row.get("road_name", "").strip()
    if rn:
        road_names[rn] = road_names.get(rn, 0) + 1

print(f"\n=== road_name 字段统计 ===")
print(f"有道路名的点: {len(road_names)} 种道路，共 {sum(road_names.values())} 个点")

# 道路名按频次排序
for name, cnt in sorted(road_names.items(), key=lambda x: -x[1]):
    print(f"  {cnt:3d}x  {name}")

# 分析 urban_form 分布
from collections import Counter
form_dist = Counter(row.get("urban_form", "") for row in rows)
print(f"\n=== urban_form 分布 ===")
for form, cnt in form_dist.most_common():
    print(f"  {form:20s}: {cnt}")

# 展示每个 urban_form 的样例
print(f"\n=== 各形态样例 ===")
for form in sorted(set(row.get("urban_form","") for row in rows)):
    samples = [r for r in rows if r.get("urban_form","") == form][:2]
    print(f"\n  [{form}]")
    for s in samples:
        print(f"    lng={s.get('lng')} lat={s.get('lat')} road={s.get('road_name')} urban={s.get('urban_form')}")
