NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# The Fig11 cell's source array ends at line 3313 with:
# '    "print(\'=\'*60)\\n",\n'
# The source array should close with ],\n (not a string)
# Then the cell object should close with },\n

# Current structure (lines 3313-3317):
# 3314: '    "  ]\\n",\n'  <- WRONG: This is a string containing the literal characters
# 3315: '  },\n'             <- Wrong: cell close should have 4-space indent
# 3316: '],\n'               <- Wrong: cells close should have 2-space indent
# 3317: ' "metadata": {\n'

# Fix:
# Line 3314 should be: '],\n' (closes source array - 3-space indent from 4-space cell indent)
# Line 3315 should be: '   },\n' (closes cell object - 3-space indent)
# Line 3316 should be: ' ],\n' (closes cells array - 2-space indent)

# But wait, looking at the error "Expecting value at line 3315"
# The issue might be that there's no comma after '},'

# Let me check: is the Fig11 cell the last cell?
# If yes, then the cells array should close with just ], (no comma)
# But if there are more cells, it should be ], (with comma)

# Actually looking at the current structure, there's no Section 13 yet
# So the Fig11 cell is the LAST cell
# The correct close should be:
# - source: ],\n
# - cell: },\n (no comma since it's last in cells array)
# - cells: ]\n (no comma since it's last in nbformat)
# - metadata: {\n...}\n

# Let me check the exact characters
print("Line 3313: %s" % repr(lines[3312]))
print("Line 3314: %s" % repr(lines[3313]))
print("Line 3315: %s" % repr(lines[3314]))
print("Line 3316: %s" % repr(lines[3315]))
print("Line 3317: %s" % repr(lines[3316]))
print("Line 3318: %s" % repr(lines[3317]))

# Fix line 3314: Remove the string wrapper, keep only the array closer
if lines[3313] == '    "  ]\\n",':
    lines[3313] = '   ],'
    print("\nFixed line 3314: changed to '   ],'")

# Fix line 3315: Add proper indentation
if lines[3314] == '  },':
    lines[3314] = '   },'
    print("Fixed line 3315: changed to '   },'")

# Fix line 3316: Should be ' ],' (2-space indent, no comma since last cell)
if lines[3315] == '],':
    lines[3315] = ' ],'
    print("Fixed line 3316: changed to ' ],'")

# Save
new_content = '\n'.join(lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("\nSaved!")

# Verify JSON
try:
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    print("SUCCESS! %d cells" % len(nb['cells']))
    
    for i, cell in enumerate(nb['cells']):
        cell_type = cell.get('cell_type', 'unknown')
        src = cell.get('source', [])
        if isinstance(src, list):
            first_line = src[0].strip()[:60] if src else '(empty)'
        else:
            first_line = str(src)[:60]
        print("  Cell %d: %s | %s" % (i, cell_type, first_line))
        
except json.JSONDecodeError as e:
    print("JSON error: %s at line %d" % (e.msg, e.lineno))
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        marker = ">>> " if i+1 == e.lineno else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
