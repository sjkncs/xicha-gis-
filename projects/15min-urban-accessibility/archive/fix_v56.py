NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Current: b'    "print(\'=\'*60)\\n"\\r"'
# Ends with: 22 5C 72 22 = quote, backslash, r, quote
# After that: 0D 0A 20 20 20 5D 2C = CR, LF, spaces, ], comma

# Line 3313 ends with: \\r"
# After \\r" comes: CR, LF, spaces, ],
# But there's no comma after \\r" to separate from the next line!

# Fix: Add comma after \\r"
# Change: 5C 72 22 0D to 5C 72 22 2C 0D

# Find \\r" followed by CR
search = bytes([0x5C, 0x72, 0x22, 0x0D])
pos = raw.find(search)
print("Pattern \\r\"<CR> at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-20:pos+30]))
    
    # Insert comma after "
    new_raw = raw[:pos+3] + b',' + raw[pos+3:]
    
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
    
    # Try without CR
    search2 = bytes([0x5C, 0x72, 0x22])
    pos2 = raw.find(search2)
    print("Pattern \\r\" at byte: %d" % pos2)
    if pos2 >= 0:
        print("Context: %s" % repr(raw[pos2-20:pos2+30]))
