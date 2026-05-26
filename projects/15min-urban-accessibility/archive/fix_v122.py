NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The problem: line 3313 ends with \n"\r",\
# The \r is literal backslash + 'r' and should be removed
# After removing: \n",\r (just the comma and CR)

# Find the pattern: 5C 6E 22 5C 72 22 2C 0D 0A
# = \n"\r",\r\n
# Should be: 5C 6E 22 2C 0D 0A = \n",\r\n

search = b'\\n"\\r",'
pos = raw.find(search)
if pos >= 0:
    print("Found '\\n\"\\r\", at raw byte %d" % pos)
    print("Before: %s" % ' '.join('%02X' % b for b in raw[pos-10:pos+15]))
    
    # Fix: remove the \r (5C 72) from the pattern
    # Current: 5C 6E 22 5C 72 22 2C
    # Should be: 5C 6E 22 2C
    old = b'\\n"\\r",'  # 5C 6E 22 5C 72 22 2C
    new = b'\\n",'       # 5C 6E 22 2C
    
    raw = raw.replace(old, new, 1)
    
    print("After:  %s" % ' '.join('%02X' % b for b in raw[pos-10:pos+15]))
    
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
    
    # Try alternative search
    search2 = b'\\r",'
    pos2 = raw.find(search2)
    if pos2 >= 0:
        print("Found '\\r\",' at raw byte %d" % pos2)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2-10:pos2+15]))
