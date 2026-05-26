NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The fix: Add comma after the last string in the source array
# Current: '"print(\'=\'*60)\\n"\\r\n   ],'
# Should be: '"print(\'=\'*60)\\n",\\r\n   ],'

# Find the exact bytes
# The last string ends with: 22 5C 72 0D 0A = " \ r CR LF
# After that comes: 20 20 20 5D 2C = spaces ] comma CR LF

old = b'"\\n"\\r\n   ],'
new = b'"\\n",\\r\n   ],'

pos = raw.find(old)
print("Looking for: %s" % repr(old))

if pos >= 0:
    print("Found at byte: %d" % pos)
    print("Context: %s" % repr(raw[pos-20:pos+40]))
    
    # Replace
    raw = raw.replace(old, new, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
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
    print("Pattern not found. Searching for similar patterns...")
    
    # Search for the pattern with different escaping
    search1 = b'"\\r\\n   ],'
    p1 = raw.find(search1)
    print("Pattern b'\"\\\\r\\\\n   ],' at: %d" % p1)
    if p1 >= 0:
        print("  Context: %s" % repr(raw[p1-20:p1+30]))
