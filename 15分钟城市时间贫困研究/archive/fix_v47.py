NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Search for: backslash (5C), r (72), CR (0D), LF (0A), spaces, ], comma
# This is: \r\n   ],

# In Python bytes: b'\\r\\n   ],' = 5C 72 0D 0A 20 20 20 5D 2C

search = bytes([0x5C, 0x72, 0x0D, 0x0A, 0x20, 0x20, 0x20, 0x5D, 0x2C])
pos = raw.find(search)
print("Pattern \\r\\n   ], at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-30:pos+40]))
    
    # Fix: Add comma after \r
    # Change: \r\n   ], to \r,\n   ],
    # In bytes: 5C 72 0D 0A -> 5C 72 2C 0D 0A
    
    # Find the exact position of 0D
    cr_pos = pos + 2  # Position of CR (after \r)
    
    # Insert comma after CR
    new_raw = raw[:cr_pos+1] + b',' + raw[cr_pos+1:]
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Fixed! Inserted comma after \\r")
    
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
    
    # Try with just CR LF
    search2 = bytes([0x0D, 0x0A, 0x20, 0x20, 0x20, 0x5D, 0x2C])
    pos2 = raw.find(search2)
    print("Pattern CR LF spaces ], at byte: %d" % pos2)
    if pos2 >= 0:
        print("Context: %s" % repr(raw[pos2-30:pos2+40]))
