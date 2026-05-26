NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find the beginning of the Fig11 cell (last source line)
# and replace from there to end of file with correct structure

# The Fig11 cell's last content is around line 3313
# Let's find where the cell started
for i in range(len(lines)):
    if 'p8_fig11' in lines[i] and 'savefig' in lines[i]:
        print("Line %d: %s" % (i+1, lines[i][:80]))

# Let me just rebuild the end correctly
# The Fig11 cell ends at line 3313 (0-indexed: 3312)
# The correct ending should be:
# Line 3313: source line (ends with "),\n")
# Line 3314: "],\n"  (closes source array)  
# Line 3315: "},\n"  (closes cell - no comma since last cell)
# Line 3316: "],\n"  (closes cells array)
# Line 3317: '"metadata": {\n' (starts metadata)
# ...

# Currently:
# Line 3312: '    "print(\'=\'*60)\\n",'  <- ends with ",\n"
# Line 3313: '    "print(\'=\'*60)\\n",'  <- This should be '    "print(\'=\'*60)\\n"\n' (no comma!)
# Line 3314: '   ],'  <- This should be '   ],\n' (has comma)
# Line 3315: '   },'  <- This should be '   },\n' (has comma)
# Line 3316: ' ],'  <- This should be ' ],\n' (has comma)

# Fix: The last source line should NOT have trailing comma
# All the closers should have commas except the last cell and cells array

# Let me just fix the specific lines
# Line 3313 (index 3312) - last source line, no comma
if lines[3312] == '    "print(\'=\'*60)\\n",':
    lines[3312] = '    "print(\'=\'*60)\\n"'
    print("Fixed last source line (removed comma)")

# Line 3314 - source array close, has comma
if lines[3313] == '   ],':
    lines[3313] = '   ],'
    print("Line 3314 already correct")

# Line 3315 - cell close, no comma (last cell)
if lines[3314] == '   },':
    lines[3314] = '   }'
    print("Fixed cell close (removed comma)")

# Line 3316 - cells array close, no comma
if lines[3315] == ' ],':
    lines[3315] = ' ]'
    print("Fixed cells array close (removed comma)")

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
