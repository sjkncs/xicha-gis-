# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

print("=== ALL CODE CELLS (index + first 60 chars) ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    first_line = src.split('\n')[0][:80] if src else '(empty)'
    print(f"  Cell {ci:2d}: {first_line}")
