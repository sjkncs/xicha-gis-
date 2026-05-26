NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find the exact location of the double backslash issue
# Looking for \\r", pattern in line 3313

# Search for the bytes: 5C 5C 72 22 2C
# = \\r",
# This should be: 5C 72 22 2C = \r",

search_pattern = b'\\r",'
pos = raw.find(search_pattern)
if pos >= 0:
    print("Found '\\r\", at raw byte %d" % pos)
    
    # Check context
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos-10:pos+20]))
    
    # The fix: replace \\r with \r
    # Position of \\r is at pos (0x5C 0x5C 0x72)
    # We need to change it to \r (0x5C 0x72)
    
    # Fix: delete the second 0x5C (at position pos+1)
    new_raw = raw[:pos+1] + raw[pos+2:]
    
    print("\nAfter fix: %s" % ' '.join('%02X' % b for b in new_raw[pos-10:pos+20]))
    
    # Save
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved.")
    
    # Test
    try:
        nb = json.loads(new_raw)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found, searching for alternatives...")
    
    # Try other patterns
    search2 = b"\\r"
    pos2 = raw.find(search2)
    if pos2 >= 0:
        print("Found '\\r' at raw byte %d" % pos2)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2-5:pos2+10]))
