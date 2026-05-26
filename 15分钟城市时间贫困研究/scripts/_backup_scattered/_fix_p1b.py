# -*- coding: utf-8 -*-
"""Fix syntax errors in p1b_overpass.py"""
import re

path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\p1b_overpass.py"
with open(path, 'rb') as f:
    data = f.read()

text = data.decode('utf-8')
lines = text.split('\n')

# Fix each problematic line
new_lines = []
for line in lines:
    # Fix 1: ~gdf_proj[...] -> res_bldg[...]
    if 'gdf_proj[~gdf_proj[' in line:
        line = line.replace(
            'gdf_proj[~gdf_proj["building"].isin(res_types)].plot',
            'gdf_proj[gdf_proj["building"].isin(res_types)].plot'
        )
    # Fix 2: v_coords = np.array(list(zip(...))) - missing )
    if 'v_coords = np.array(list(zip(villages["lng"], villages["lat"]))' in line:
        line = line + ')'
    # Fix 3: remove check_outputs import
    if 'check_outputs,' in line:
        line = line.replace('    check_outputs,\n', '')
    new_lines.append(line)

new_text = '\n'.join(new_lines)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)

# Verify
import ast
try:
    ast.parse(new_text)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Error at line {e.lineno}: {e.msg}")
    for i in range(max(0, e.lineno-3), min(len(new_lines), e.lineno+2)):
        marker = '>>> ' if i+1 == e.lineno else '    '
        print(f"{marker}{i+1}: {new_lines[i][:100]}")
