# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NB = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

# Read Cell 19 full content
src19 = ''.join(nb['cells'][19]['source'])
print("Cell 19 ({} lines):".format(src19.count('\n')+1))
print("=" * 70)
print(src19)
