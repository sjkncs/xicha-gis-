# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Find cells with NetworkDistanceCalculator and build_od_matrix
print("=== NetworkDistanceCalculator + OD matrix cells ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'build_od_matrix' in src or 'NetworkDistanceCalculator' in src:
        print(f"\nCell {ci} ({len(cell['source'])} lines):")
        for li, line in enumerate(cell['source'][:5]):
            print(f"  {li}: {line.rstrip()[:80]}")
        print("  ...")

# Find cells with Gaussian2SFCA
print("\n=== Gaussian2SFCA cells ===")
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'Gaussian2SFCA' in src or 'gaussian' in src.lower() and '2SFCA' in src:
        print(f"\nCell {ci} ({len(cell['source'])} lines):")
        for li, line in enumerate(cell['source'][:3]):
            print(f"  {li}: {line.rstrip()[:80]}")
