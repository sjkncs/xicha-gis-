# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Show cell 28 (acc_results construction + communities_gdf merge)
cell28 = nb['cells'][28]
print("=== CELL 28 (acc_results + communities merge) - FULL ===")
for li, line in enumerate(cell28['source']):
    print(f"  {li:3d}: {line.rstrip()}")
