NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# The problem: Line 3314 has literal `],` but should have proper JSON:
# Line 3314 should be: `    "  ]\n",`  (close source array with escaped newline in string)
# Line 3315 should be: `  },\n` (close cell object)
# Lines 3316-3323 should be REMOVED (broken Section 13 content)
# Line 3324 should be: `],\n` (close cells array)

# But currently:
# Line 3313: `'    "print(\'=\'*60)\\n",\n'` - last source string of Fig11 cell
# Line 3314: `'   ],\n'` - wrong! Should be: `    "  ]\n",\n`  (string with escaped newline)
# Line 3315: `'  },\n'` - wrong! Should be: `  },\n`  (close cell)
# Lines 3316-3322: broken Section 13 content
# Line 3323: `' ],\n'` - close cells array
# Line 3324: `' "metadata": {\n'` - metadata

# Fix:
# 1. Change line 3314 from `'   ],\n'` to `'    "  ]\\n",\n'`
# 2. Change line 3315 from `'  },\n'` to `'  },\n'` (keep as is but remove trailing ,)
# 3. Delete lines 3316-3322 (broken Section 13 content)
# 4. Keep line 3323 (now 3324 after delete) as `],\n`
# 5. Keep line 3324 (now 3325) as `"metadata": {\n`

print("Before fix:")
print("Line 3314: %s" % repr(lines[3313]))
print("Line 3315: %s" % repr(lines[3314]))
print("Line 3316: %s" % repr(lines[3315]))
print("Line 3317: %s" % repr(lines[3316]))
print("...")

# Fix line 3314
if lines[3313] == '   ],':
    lines[3313] = '    "  ]\\n",'
    print("\nFixed line 3314")

# Fix line 3315 - should not have trailing comma
if lines[3314] == '  },':
    lines[3314] = '  },'
    print("Fixed line 3315 (removed trailing comma)")

# Delete lines 3316-3322 (broken Section 13 content)
# These are indices 3315-3321 (0-based)
broken_content = lines[3315:3322]
print("\nRemoving broken Section 13 content (%d lines):" % len(broken_content))
for i, line in enumerate(broken_content):
    print("  Line %d: %s" % (3316+i, repr(line[:50])))

del lines[3315:3322]
print("\nAfter deletion, total lines: %d" % len(lines))

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
