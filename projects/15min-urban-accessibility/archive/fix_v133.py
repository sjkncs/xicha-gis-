NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The issue: line 3314 has ], (comma before ]) which is a trailing comma
# This should just be ] (no comma)

# Find the pattern: ], followed by } and CRLF
# That is: 5D 2C 0D 0A 20 20 20 7D
search = b'],\r\n   }'
pos = raw.find(search)
if pos >= 0:
    print("Found '],\\r\\n   }' at raw byte %d" % pos)
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos-5:pos+20]))
    
    # Fix: replace ],\r\n with ]\r\n
    # Pattern: 5D 2C 0D 0A -> 5D 0D 0A
    old = b'],\r\n   '  # ],\r\n   (with 3 spaces)
    new = b']\r\n   '   # ]\r\n   (with 3 spaces)
    
    raw = raw.replace(old, new, 1)
    print("Fixed!")
    
    # Save
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("Saved.")
    
    # Test
    try:
        nb = json.loads(raw)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found")
    
    # Try alternative pattern
    search2 = b'],\r\n'
    pos2 = raw.find(search2)
    if pos2 >= 0:
        print("Found '],\\r\\n' at raw byte %d" % pos2)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2-5:pos2+15]))
