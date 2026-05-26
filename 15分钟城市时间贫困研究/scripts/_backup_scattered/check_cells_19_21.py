# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Show last 15 lines of Cell 19
cell = nb['cells'][19]
src = ''.join(cell['source'])
lines = src.split('\n')
print("=== CELL 19 (last 20 lines) ===")
for li, line in enumerate(lines[-20:]):
    print(f"{li:3d}|{line}")

# Show last 15 lines of Cell 21 (vectorized)
cell21 = nb['cells'][21]
src21 = ''.join(cell21['source'])
lines21 = src21.split('\n')
print("\n=== CELL 21 (last 20 lines) ===")
for li, line in enumerate(lines21[-20:]):
    print(f"{li:3d}|{line}")
