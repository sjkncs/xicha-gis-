NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

print("File size: %d bytes" % len(raw))

# The problem: inside the source array, there's a whitespace-only line
# Pattern: b',\r\n    \r\n'
# This should be: b',\r\n' (just remove the whitespace line)

# Search for the specific pattern
old = b',\r\n    \r\n'
new = b',\r\n'
pos = raw.find(old)
print("Pattern b',\\r\\n    \\r\\n' at byte: %d" % pos)

if pos >= 0:
    print("Before: %s" % repr(raw[pos-20:pos+30]))
    
    # Fix
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
    print("Pattern not found")
    
    # Search for similar patterns
    search2 = b'\r\n    \r\n'
    positions = []
    start = 0
    while True:
        p = raw.find(search2, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
        if len(positions) > 20:
            break
    
    print("\nAll occurrences of '\\r\\n    \\r\\n':")
    for p in positions:
        print("  byte %d: %s" % (p, repr(raw[p-10:p+20])))
