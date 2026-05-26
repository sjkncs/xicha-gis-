# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Check POI cell (index 13)
cell13 = nb['cells'][13]
print("=== POI CELL (index 13) - first 60 lines ===")
for i, line in enumerate(cell13['source'][:60]):
    print(f"  {i:3d}: {repr(line)[:100]}")

# Also check what nanshan_poi references exist
print("\n\n=== ALL nanshan_poi references ===")
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    for j, line in enumerate(cell['source']):
        if 'nanshan_poi' in line:
            print(f"  Cell {i}, Line {j}: {repr(line)[:100]}")
