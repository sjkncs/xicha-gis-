# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

print("=== First 5 code cells ===")
for ci, cell in enumerate(nb['cells'][:15]):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'import' in src[:200] or 'from' in src[:200]:
        print(f"\nCell {ci} (first 200 chars):")
        print(src[:300])
