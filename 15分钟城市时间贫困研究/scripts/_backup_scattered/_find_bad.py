# -*- coding: utf-8 -*-
import sys
path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\p0_rebuild_night.py"
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
lines = text.split('\n')
# Find problematic line
for i, line in enumerate(lines):
    if 'is_night_true(row.get("night_service"))' in line and line.count(')') > line.count('('):
        print(f"Line {i+1}: {line}")
