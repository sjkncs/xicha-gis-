# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NB = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']

# Check Cell 13: POI loading + supply init
c13 = ''.join(cells[13]['source'])
print("=== Cell 13 (POI loading) ===")
print(c13[:2000])
print("...")

# Check Cell 19: supply init
c19 = ''.join(cells[19]['source'])
print("\n=== Cell 19 (supply init) ===")
for line in c19.splitlines():
    if 'supply' in line.lower() or 'population' in line.lower():
        print(" ", line.strip())

# Check Cell 25: key lines
c25 = ''.join(cells[25]['source'])
print("\n=== Cell 25 (key lines) ===")
for line in c25.splitlines():
    if any(kw in line for kw in ['acc_results', 'poi_df', 'effective_supply', 'run_multi', 'TPI']):
        print(" ", line.strip()[:100])

# Check all cells for 'acc_results'
print("\n=== Cells referencing 'acc_results' ===")
for i, c in enumerate(cells):
    src = ''.join(c['source'])
    if 'acc_results' in src:
        print(f"  Cell {i}: first mention at pos {src.find('acc_results')}")
