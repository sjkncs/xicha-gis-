"""
对比 n201 和 n188 的坐标精度差异，看是否能用容差匹配
"""
import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

n201_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "integrated_collection" / "samples" / "sample_points_n201.csv"
n188_path = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview" / "samples" / "sample_points_n188.csv"

# Load n201
n201_list = []
with open(n201_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lng = float(row["lng"]); lat = float(row["lat"])
            n201_list.append((lng, lat, row.get("urban_form","")))
        except: pass

# Load n188
n188_list = []
with open(n188_path, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            lng = float(row["lng"]); lat = float(row["lat"])
            addr = row.get("常用地址","")
            n188_list.append((lng, lat, addr))
        except: pass

print(f"n201: {len(n201_list)} points")
print(f"n188: {len(n188_list)} points")

# Check if any n201 coords are in n188 (with 1e-5 tolerance)
matched = 0
unmatched_examples = []
for i, (l1, la1, form1) in enumerate(n201_list[:10]):
    found = False
    for l2, la2, addr2 in n188_list:
        if abs(l1-l2) < 1e-5 and abs(la1-la2) < 1e-5:
            found = True
            matched += 1
            break
    if not found:
        unmatched_examples.append((l1, la1, form1))

print(f"\nMatched (1e-5 tol): {matched} / 10 shown")
for l,la,f in unmatched_examples:
    print(f"  n201: lng={l}, lat={la}, form={f}")

# Also: check n188 unique address prefixes
print("\n=== n188 地址前缀（前20个）===")
prefixes = set()
for l,la,addr in n188_list:
    if addr:
        prefix = addr[:4]
        prefixes.add(prefix)
        if len(prefixes) <= 20:
            print(f"  {addr[:30]}")
