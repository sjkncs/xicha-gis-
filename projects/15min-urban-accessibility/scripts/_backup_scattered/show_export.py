# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Show full export cell (index 35)
cell = nb['cells'][35]
print("=== EXPORT CELL (index 35) - FULL ===")
for i, line in enumerate(cell['source']):
    print(f"  {i:3d}: {line.rstrip()}")

# Also find all cells that reference SDI or vulnerability_level
print("\n=== SDI/vulnerability_level references ===")
for ci, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'SDI' in src or 'vulnerability_level' in src or 'SDI_elderly' in src:
        print(f"\nCell {ci}:")
        for li, line in enumerate(cell['source']):
            if any(kw in line for kw in ['SDI', 'vulnerability_level']):
                print(f"  {li}: {line.rstrip()[:120]}")
