# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NB = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']
# Read cell 25 fully
cell25 = cells[25]
src25 = ''.join(cell25['source'])
print("Cell 25 full content ({} lines):".format(src25.count('\n')+1))
print("=" * 70)
print(src25[:5000])
if len(src25) > 5000:
    print(f"\n... (+{len(src25)-5000} more chars)")
    print("=" * 70)
    print(src25[-3000:])
