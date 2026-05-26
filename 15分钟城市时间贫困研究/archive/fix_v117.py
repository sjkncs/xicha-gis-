NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find the pattern: 5C 6E 22 5C 22 2C
# That is: \n"\"",
# Should be: \n",
search = b'\\n"\\"'
pos = raw.find(search)
if pos >= 0:
    print("Found '\\n\"\\\"' at raw byte %d" % pos)
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos-5:pos+15]))
    
    # Fix: remove the 5C before the 22 (the extra backslash)
    # Current: 5C 6E 22 5C 22 2C
    # Target:  5C 6E 22 22 2C
    new_raw = raw[:pos+3] + raw[pos+4:]  # Remove byte at pos+3 (the 5C)
    
    print("After fix: %s" % ' '.join('%02X' % b for b in new_raw[pos-5:pos+15]))
    
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
    print("Pattern not found")
    
    # Search for just the bad quote pattern
    search2 = b'"\\"'
    pos2 = raw.find(search2)
    if pos2 >= 0:
        print("Found quote-backslash-quote at raw byte %d" % pos2)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2-5:pos2+10]))
