# -*- coding: utf-8 -*-
import ast

files = {
    'Cell 18 (NetworkDistanceCalculator)': r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\apply_opt_cells.py',
}

# Read the new cell code from the script
with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\apply_opt_cells.py', encoding='utf-8') as f:
    script = f.read()

# Extract just the new cell strings
import re
m18 = re.search(r"new_cell18 = '''(.*?)'''", script, re.DOTALL)
m23 = re.search(r"new_cell23 = '''(.*?)'''", script, re.DOTALL)

if m18:
    code18 = m18.group(1).replace('\\n', '\n')
    try:
        ast.parse(code18)
        print('Cell 18 syntax: PASSED')
    except SyntaxError as e:
        print(f'Cell 18 ERROR: {e}')
        lines = code18.split('\n')
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = '>>> ' if i+1 == e.lineno else '    '
            print(f'{marker}{i+1}: {lines[i][:100]}')

if m23:
    code23 = m23.group(1).replace('\\n', '\n')
    try:
        ast.parse(code23)
        print('Cell 23 syntax: PASSED')
    except SyntaxError as e:
        print(f'Cell 23 ERROR: {e}')

# Check cell 21
with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\fix_cells_19_21.py', encoding='utf-8') as f:
    script21 = f.read()
m21 = re.search(r"new_cell21 = '''(.*?)'''", script21, re.DOTALL)
if m21:
    code21 = m21.group(1).replace('\\n', '\n')
    try:
        ast.parse(code21)
        print('Cell 21 syntax: PASSED')
    except SyntaxError as e:
        print(f'Cell 21 ERROR: {e}')
        lines = code21.split('\n')
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = '>>> ' if i+1 == e.lineno else '    '
            print(f'{marker}{i+1}: {lines[i][:100]}')

print("\nAll modified cells syntax checked!")
