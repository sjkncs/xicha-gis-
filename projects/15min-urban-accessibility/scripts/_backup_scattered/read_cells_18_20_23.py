# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

for ci in [18, 20, 23]:
    cell = nb['cells'][ci]
    print(f"\n{'='*70}")
    print(f"CELL {ci}")
    print('='*70)
    for li, line in enumerate(cell['source']):
        print(f"{li:3d}|{line}", end='')
