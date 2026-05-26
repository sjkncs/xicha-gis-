NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Check lines 3310-3320
print("Lines 3308-3320:")
for i in range(3307, 3320):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i])))

# Now let me understand: is line 3313 the LAST element of the source array?
# If line 3314 is `   ],` then line 3313 should NOT have a comma

# Current line 3313: `'    "print(\'=\'*60)\\n"\\r",'`
# This ends with a comma - should it?

# Line 3314: `   ],` - this closes the source array
# So line 3313 IS the last element
# The comma after line 3313 should be REMOVED

print("\n\nFixing: Remove comma from line 3313 (it's the last element)")

# Current: '    "print(\'=\'*60)\\n"\\r",'
# Fix: '    "print(\'=\'*60)\\n"\\r"'

# Find and fix
old = b'    "print(\'=\'*60)\\n"\\r",'
new = b'    "print(\'=\'*60)\\n"\\r"'

pos = raw.find(old)
print("Pattern at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-20:pos+40]))
    
    new_raw = raw.replace(old, new, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Fixed!")
    
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
else:
    print("Pattern not found exactly. Searching for similar...")
    
    # Search for the print statement without the comma check
    search = b"print('='*60)"
    positions = []
    start = 0
    while True:
        p = raw.find(search, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
    
    for p in positions:
        chunk = raw[p:p+50]
        print("  byte %d: %s" % (p, repr(chunk)))
