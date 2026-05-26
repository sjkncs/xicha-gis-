NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# From hex dump:
# Current:    "    },\r\n     ],\r\n "metadata"
# Should be:  "  },\r\n],\r\n "metadata"
#
# Hex breakdown:
# 20 20 20 20 22 20 7D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A 20 22 6D
# =     " },\r\n     ],\r\n "m

# Fix: Remove 2 spaces from '    },' and remove 4 spaces from '     ],'
BROKEN = b'    " },\r\n     ],'
FIXED = b'  },\r\n],'

pos = raw.find(BROKEN)
print("Broken pattern at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-10:pos+50]))
    print("\nApplying fix...")
    new_raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved!")
    
    # Verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Still broken: %s at line %d" % (e.msg, e.lineno))
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found. Let me find what's actually there...")
    
    # Search for the Section 13 header area
    idx = raw.find(b"id='13'")
    if idx >= 0:
        # Show 100 bytes from there
        area = raw[idx:idx+150]
        print("Section 13 area (%d bytes):" % len(area))
        print(' '.join('%02X' % b for b in area))
        print(repr(area.decode('utf-8', errors='replace')))
        
        # Find the pattern with "},\r\n" near "metadata"
        # Search for the actual closing pattern
        close_patterns = [
            b'},\r\n     ],',
            b'},\r\n ],',
            b'},\r\n ],\r\n',
            b'    },\r\n     ],',
        ]
        for p in close_patterns:
            count = raw.count(p)
            if count > 0:
                print("'%s' found %d times" % (repr(p), count))
                # Show position
                pos = raw.find(p)
                print("  First at byte %d: %s" % (pos, repr(raw[pos:pos+len(p)+30])))
