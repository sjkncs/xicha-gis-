# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find where communities_gdf gets merged into acc_gdf
print("=== communities_gdf merge ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    for li, line in enumerate(cell['source']):
        if 'communities_gdf' in line and ('acc_gdf' in line or 'merge' in line or 'join' in line):
            print(f"  Cell {ci}, Line {li}: {line.rstrip()[:120]}")
        elif 'acc_gdf' in line and ('=' in line) and ('communities_gdf' not in line):
            pass  # skip minor refs

# Find cell 29 (2SFCA results cell) full content
print("\n=== CELL 29 (2SFCA results) - full ===")
cell29 = nb['cells'][29]
for li, line in enumerate(cell29['source']):
    print(f"  {li:3d}: {line.rstrip()[:120]}")

# Find vulnerable profiler cell output
print("\n=== Vulnerable profiler cell (cell 18) last lines ===")
cell18 = nb['cells'][18]
for li, line in enumerate(cell18['source'][-20:]):
    print(f"  {len(cell18['source'])-20+li:3d}: {line.rstrip()[:120]}")
