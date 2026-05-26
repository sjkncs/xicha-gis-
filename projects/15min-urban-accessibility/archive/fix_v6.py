NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# Find Section 13 area
idx = raw.find(b"id='13'")
if idx >= 0:
    print("id='13' at byte: %d" % idx)
    # Show 200 bytes from there
    area = raw[idx:idx+200]
    decoded = area.decode('utf-8', errors='replace')
    print("\nDecoded context:")
    print(repr(decoded))
    
    # Now look at raw hex
    print("\nRaw hex:")
    for i in range(0, min(len(area), 200), 32):
        chunk = area[i:i+32]
        hex_part = ' '.join('%02X' % b for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print('%04X: %-96s | %s' % (idx+i, hex_part, ascii_part))

# Now try the actual fix
print("\n=== Attempting fix ===")

# The broken pattern in raw bytes is:
# After the Section 13 content "  ]\n",\r\n
# "    },\r\n ],\r\n "metadata"
# This is: 22 20 20 20 20 7D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A 20 20 22

# The correct pattern should be:
# "  },\r\n],\r\n "metadata"
# Which is: 22 20 20 7D 2C 0D 0A 5D 2C 0D 0A 20 20 22

# But looking at the hex dump from earlier:
# 28B08: 22 20 7D 2C 0D 0A 20 5D 2C 0D 0A 20 22 6D
# That's: " }, CRLF ], CRLF "metadata

# So the file ALREADY has correct structure: " },\r\n ],\r\n "metadata"
# But the indentation on ' ],' has 4 spaces instead of 2

# The broken pattern is: 22 20 20 20 20 7D 2C 0D 0A 20 20 20 20 5D 2C
# Which is: "     },\r\n     ],\r\n
# Wait no, looking again at the JSON error output:
# Line 3322: '    " },' (4 spaces before ")
# Line 3323: ' ],' (2 spaces before ])

# The fix should change '    " },' to '  },'
# That means: 22 20 20 20 20 7D 2C -> 22 20 20 7D 2C

BROKEN = b'"    },\r\n'
FIXED = b'"  },\r\n'

pos = raw.find(BROKEN)
print("Pattern '\"    },\\r\\n' at byte: %d" % pos)

if pos >= 0:
    print("Found! Applying fix...")
    print("Context: %s" % repr(raw[pos-20:pos+40]))
    new_raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved!")
    
    # Verify
    import json
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
    print("Pattern not found.")
    
    # Search for just ' },' followed by CRLF
    search = b' },\r\n'
    count = raw.count(search)
    print("' },\\r\\n' occurs %d times" % count)
    
    # Show positions
    start = 0
    for i in range(min(count, 10)):
        p = raw.find(search, start)
        if p >= 0:
            print("  byte %d: %s" % (p, repr(raw[p-5:p+20])))
            start = p + 1
