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
    if 'class TwoStepFloatingCatchmentArea' in src:
        print(f"Cell {ci} - TwoStepFloatingCatchmentArea:")
        for li, line in enumerate(cell['source']):
            print(f"{li:3d}|{line}", end='')
        print()
        print("="*70)
