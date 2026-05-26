NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

print("File size: %d bytes" % len(raw))

# From the hex dump:
# Line 3313 ends with: 22 2C 0D = " ,
# This means the line has literal '"' + ',' + CR
# The string should end with just '"'
# And CR should be escaped as \r

# Fix: Find '",\r' and replace with '"\r' (remove comma)
# OR find '"  ],\r' and replace with '"]\r' (remove comma before ])

# But wait, looking at the structure:
# Line 3313: '    "print(\'=\'*60)\\n",\r' <- This is INSIDE the source array
# Line 3314: '   ],\r' <- This closes the source array

# The issue: Line 3313 has a trailing comma which is valid for JSON array elements
# But the LAST element in an array should NOT have a trailing comma!

# So the fix is: Remove the comma from line 3313 (the LAST element)
# Change: '    "print(\'=\'*60)\\n",\r' 
# To: '    "print(\'=\'*60)\\n"\r'

# But wait - is line 3313 really the last element?
# Let me check if there's more content after

# Search for '",\r' followed by '   ],\r'
# In bytes: 22 2C 0D followed by 20 20 20 5D 2C

search = b'",\r\n   ],'
pos = raw.find(search)
print("Pattern '\",\\r\\n   ],' at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-20:pos+30]))
    
    # The fix: Change '",\r\n   ],' to '"\\r\n   ],'
    # This removes the comma after the last string
    
    new_raw = raw.replace(b'",\r\n   ],', b'"\\r\n   ],', 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved!")
    
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
    
    # Let me search for just the comma pattern
    search2 = b'",\r\n'
    positions = []
    start = 0
    while True:
        p = raw.find(search2, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
        if len(positions) > 5:
            break
    
    print("\nFound %d occurrences of ',\\r\\n'" % len(positions))
    for p in positions[-5:]:
        print("  byte %d: %s" % (p, repr(raw[p-10:p+20])))
