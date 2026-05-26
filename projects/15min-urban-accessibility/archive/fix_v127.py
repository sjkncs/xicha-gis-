NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The issue: at raw byte 166417, we have:
# print('='*60)\n",\r\n\n   ],
#                                        ^^ extra LF
# We need to remove one LF

search = b"print('='*60)"
pos = raw.find(search)
if pos >= 0:
    print("Found at raw byte %d" % pos)
    
    # Context
    print("Context bytes %d-%d:" % (pos, pos+30))
    print(' '.join('%02X' % b for b in raw[pos:pos+30]))
    
    # The pattern: 29 5C 6E 22 2C 0D 0A 0A 20 20 20 5D 2C
    # = ) \ n " , CR LF LF [space][space][space] ] ,
    # We need to remove one LF: 0D 0A 0A -> 0D 0A
    
    # Current: 2C 0D 0A 0A 20
    # Should be: 2C 0D 0A 20
    old = b'\x2c\x0d\x0a\x0a\x20'  # ,\r\n\n
    new = b'\x2c\x0d\x0a\x20'  # ,\r\n
    
    # But we need to match exactly - let me check
    check_start = pos + 16  # position of the comma
    print("\nBytes at check position: %s" % ' '.join('%02X' % b for b in raw[check_start:check_start+6]))
    
    if raw[check_start:check_start+5] == old:
        print("Found pattern to fix!")
        raw = raw[:check_start] + new + raw[check_start+5:]
        print("Fixed.")
    else:
        print("Pattern not found exactly, trying alternative...")
        # Try different offset
        for offset in range(-3, 4):
            check = pos + 16 + offset
            if raw[check:check+5] == old:
                print("Found at offset %d!" % offset)
                raw = raw[:check] + new + raw[check+5:]
                break
    
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
