NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# From the structure analysis:
# Line 3312: '    "print(\'=\'*60)\\n",\r' <- ends with comma, OK
# Line 3313: '    "print(\'=\'*60)\\n"\\r' <- MISSING comma after quote!

# The pattern after line 3313 is: 
# b'\\n"\\r\\n   ],' 
# Which in JSON means: \n (escaped) + " (quote) + \r (escaped) + LF + spaces + ],

# Current: b'\\n"\\r\n   ],'
# Fix: Add comma after " -> b'\\n",\\r\n   ],'

# But wait, in the raw file, what exactly are the bytes?
# Let me find the exact sequence

# The last source string element ends with: \\n"\\r
# Then follows: \n   ],

# Fix: Change \\r\n   ], to \\r,\n   ], (add comma after \r, before \n)
old = b'\\r\\n   ],'
new = b'\\r,\\n   ],'

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
    print("Pattern not found. Let me search for similar patterns...")
    
    # Search for just \\r\\n
    search2 = b'\\r\\n'
    positions = []
    start = 0
    while True:
        p = raw.find(search2, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
        if len(positions) > 10:
            break
    
    print("Found %d occurrences of \\r\\n" % len(positions))
    for p in positions[-5:]:
        print("  byte %d: %s" % (p, repr(raw[p-20:p+40])))
