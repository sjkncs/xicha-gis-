# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Show the full POI cell (index 13) - all lines
cell13 = nb['cells'][13]
print("=== POI CELL (index 13) - FULL ===")
for i, line in enumerate(cell13['source']):
    print(f"  {i:3d}: {repr(line)}")
