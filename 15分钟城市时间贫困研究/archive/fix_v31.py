NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Context around line 3313
print("\nLines 3310-3320:")
for i in range(3309, min(3320, len(lines))):
    print("%d: %s" % (i+1, repr(lines[i])))

# Fix line 3313 (index 3312) - add missing comma
line = lines[3312]
if line.endswith('"'):
    lines[3312] = line + ','
    print("\nFixed line 3313: added comma")
elif line.endswith('\\n"'):
    lines[3312] = line.replace('\\n"', '\\n",')
    print("\nFixed line 3313: added comma after \\n")
else:
    print("Unexpected line format: %s" % repr(line))

# Save
new_content = '\n'.join(lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Saved!")

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
