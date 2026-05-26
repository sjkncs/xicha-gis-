# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find cells with acc_gdf references
print("=== acc_gdf construction/merge ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    for li, line in enumerate(cell['source']):
        if 'acc_gdf' in line and ('=' in line or 'merge' in line or 'join' in line or 'concat' in line):
            print(f"  Cell {ci}, Line {li}: {line.rstrip()[:120]}")

# Show last 30 lines of cell 33 (equity/moran section before export)
print("\n=== CELL 33 (before export) - last 40 lines ===")
cell33 = nb['cells'][33]
for li, line in enumerate(cell33['source'][-40:]):
    print(f"  {len(cell33['source'])-40+li:3d}: {line.rstrip()[:120]}")
