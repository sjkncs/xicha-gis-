# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find the imports cell - look for 'import numpy' or 'import networkx'
import_cell = None
for ci, cell in enumerate(nb['cells'][:20]):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'import numpy' in src or 'import networkx' in src or 'from scipy' in src:
        import_cell = ci
        print(f"Import cell found at index {ci}:")
        print(src[:800])
        print("\n...")
        break

# Also check for WALK_SPEED_M_PER_MIN
print("\n\n=== Search for WALK_SPEED_M_PER_MIN ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'WALK_SPEED' in src:
        print(f"Cell {ci}: found WALK_SPEED")
        for line in src.split('\n')[:5]:
            print(f"  {line[:100]}")
        break
