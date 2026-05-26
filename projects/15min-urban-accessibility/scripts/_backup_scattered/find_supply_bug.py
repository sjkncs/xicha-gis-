# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'np.random.uniform(0.5, 1.0, size=len(poi_df))' in src:
        print(f"Cell {ci}: Found supply random override!")
        print("Last 10 lines:")
        lines = src.split('\n')
        for li in lines[-10:]:
            print(f"  {li[:120]}")
        print()
