# -*- coding: utf-8 -*-
"""直接修复 p0_rebuild_night.py 中的语法错误"""
import re

path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\p0_rebuild_night.py"

with open(path, encoding='utf-8') as f:
    content = f.read()

# Fix 1: line 155 - is_night_true missing closing )
content = content.replace(
    'is_night_true(row.get("night_service"))',
    'is_night_true(row.get("night_service")))'
)

# Fix 2: line 242 - unbalanced [ in boolean mask
content = content.replace(
    'gaode[(gaode["v5_matched"]) & (gaode["night_service"].apply(is_night_true) == True)]',
    'gaode[(gaode["v5_matched"]) & (gaode["night_service"].apply(is_night_true) == True)]'
)
# The actual problem is one extra [ 
content = content.replace(
    'gaode[(gaode["v5_matched"]) &',
    'gaode[(gaode["v5_matched"]) &'
)

# Let me check what's on line 242 more carefully
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'v5_matched"])' in line:
        print(f"Line {i+1}: {line[:120]}")

# Check line 241-243
for i in range(239, 245):
    if i < len(lines):
        print(f"  {i+1}: {lines[i][:120]}")

# Fix: replace the broken boolean mask
content = content.replace(
    'night_v5_direct = int(gaode[(gaode["v5_matched"]) & (gaode["night_service"].apply(is_night_true) == True)].shape[0])',
    'night_v5_direct = int(gaode[(gaode["v5_matched"]==True) & (gaode["night_service"].apply(is_night_true) == True)].shape[0])'
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify syntax
import ast
try:
    ast.parse(content)
    print("Syntax OK!")
except SyntaxError as e:
    print(f"Syntax error at line {e.lineno}: {e.msg}")
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        marker = '>>> ' if i+1 == e.lineno else '    '
        print(f'{marker}{i+1}: {lines[i][:100]}')
