"""
快速扫描：加载 n201 + n188，对比字段，找出如何合并。
"""
import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

n201_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n201.csv"
n188_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "samples" / "sample_points_n188.csv"

print("=== n201 字段 ===")
with open(n201_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    print(f"Headers: {reader.fieldnames}")
    row1 = next(reader)
    print(f"Sample: lng={row1.get('lng')}, lat={row1.get('lat')}, urban_form={row1.get('urban_form')}")

print("\n=== n188 字段 ===")
with open(n188_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    print(f"Headers: {reader.fieldnames}")
    row1 = next(reader)
    print(f"Sample:")
    for k, v in row1.items():
        if v.strip():
            print(f"  {k}: {v}")

print("\n=== 坐标匹配测试 (n201 vs n188) ===")
# Load n188 with coordinates
n188_by_coord = {}
with open(n188_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lng = float(row["lng"]); lat = float(row["lat"])
            n188_by_coord[(round(lng,7), round(lat,7))] = row
        except: pass

print(f"n188 loaded: {len(n188_by_coord)} points")

# Match n201 coords
n201_path_check = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n201.csv"
matched = 0
with open(n201_path_check, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lng = float(row["lng"]); lat = float(row["lat"])
            key = (round(lng,7), round(lat,7))
            if key in n188_by_coord:
                matched += 1
                if matched == 1:
                    n188 = n188_by_coord[key]
                    print(f"First match found:")
                    print(f"  n201 urban_form: {row.get('urban_form')}")
                    print(f"  n188 address: {n188.get('常用地址')}")
                    print(f"  n188 name: {n188.get('名称')}")
                    print(f"  n188 building: {n188.get('building_name')}")
                    print(f"  n188 addr_code: {n188.get('统一地址编码')}")
        except: pass

print(f"\nTotal matched: {matched} / 201")
