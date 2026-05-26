# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find all night_service and supply references
print("=== night_service / supply / FACILITY references ===")
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    for j, line in enumerate(cell['source']):
        if any(kw in line for kw in ['night_service', 'FACILITY_NIGHT', 'supply', 'FACILITY_TYPE']):
            print(f"  Cell {i:2d}, Line {j:3d}: {line.rstrip()[:100]}")

# Also check cell 13 (POI loading) structure more carefully
print("\n=== CELL 13 full structure ===")
cell13 = nb['cells'][13]
for j, line in enumerate(cell13['source']):
    print(f"  {j:3d}: {line.rstrip()[:100]}")
