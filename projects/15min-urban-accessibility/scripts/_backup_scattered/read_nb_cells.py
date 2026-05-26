# -*- coding: utf-8 -*-
"""Read notebook cell contents for planning integration"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = json.load(open(r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb", encoding='utf-8'))
cells = nb['cells']

for idx in [12, 13, 19, 20, 21, 23, 25]:
    cell = cells[idx]
    src = ''.join(cell.get('source', []))
    print(f"\n{'='*70}")
    print(f"Cell {idx} ({cell.get('cell_type','')})")
    print(f"{'='*70}")
    # Show first 30 lines
    lines = src.strip().split('\n')
    for i, line in enumerate(lines[:35]):
        print(f"  {i+1:2}: {line[:120]}")
    if len(lines) > 35:
        print(f"  ... (+{len(lines)-35} more lines)")
