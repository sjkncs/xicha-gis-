NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read as text
with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Line 3322 is index 3321 (0-based)
# Should be '    },\n' not '  },\n'
print("\nBefore fix:")
print("Line 3322: '%s'" % lines[3321])
print("Line 3323: '%s'" % lines[3322])
print("Line 3324: '%s'" % lines[3323])

# Fix: Replace '  },\n' with '    },\n' at line 3322 (index 3321)
if lines[3321] == '  },\n':
    lines[3321] = '    },\n'
    print("\nFixed indentation!")
elif lines[3321] == '  },\r\n':
    lines[3321] = '    },\r\n'
    print("\nFixed indentation (with CR)!")

print("\nAfter fix:")
print("Line 3322: '%s'" % lines[3321])
print("Line 3323: '%s'" % lines[3322])
print("Line 3324: '%s'" % lines[3323])

# Save
new_content = '\n'.join(lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("\nSaved!")

# Verify
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
    print("Still broken: %s at line %d" % (e.msg, e.lineno))
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        marker = ">>> " if i+1 == e.lineno else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
