NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# The broken pattern: cell close has wrong indentation and cells close has extra space
# Current: '    },\r\n ],\r\n "metadata"'
# Should be: '  },\r\n],\r\n "metadata"'
# Where the extra space on ' ],' is the problem

# Search for the broken pattern
BROKEN = b'    },\r\n ],\r\n "metadata"'
FIXED = b'  },\r\n],\r\n "metadata"'

pos = raw.find(BROKEN)
print("Broken pattern at byte: %d" % pos)

if pos >= 0:
    print("Found! Applying fix...")
    raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    
    print("File saved!")
    
    # Verify JSON
    import json
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS: JSON is valid! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Still broken: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
        # Show context around error
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-5), min(len(lines), e.lineno+3)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found. Let me search for alternatives...")
    
    # Try without trailing space
    alt = b'    },\r\n ],\r\n'
    alt_pos = raw.find(alt)
    print("Alt pattern (no metadata) at byte: %d" % alt_pos)
    
    # Try with 4-space indent on ],
    alt2 = b'    },\r\n    ],\r\n'
    alt2_pos = raw.find(alt2)
    print("Alt2 pattern at byte: %d" % alt2_pos)
    
    # Let's just show what's at the end of the file
    print("\nLast 500 bytes of file (decoded):")
    end = raw[-500:].decode('utf-8', errors='replace')
    print(repr(end))
