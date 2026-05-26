# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find poi_df column references across all code cells
print("=== poi_df column references across all cells ===")
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell['source'])
    if 'poi_df' not in src:
        continue
    for j, line in enumerate(cell['source']):
        if 'poi_df' in line and ('column' in line or "'" in line or '"' in line):
            print(f"  Cell {i}, Line {j}: {line.rstrip()}")
