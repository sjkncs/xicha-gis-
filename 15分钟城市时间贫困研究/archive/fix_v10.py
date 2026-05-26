NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# From hex dump analysis:
# Current: 20 20 20 20 22 20 7D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A
# = "    " },\r\n     ],\r\n
# Should be: 20 20 22 20 7D 2C 0D 0A 5D 2C 0D 0A
# = "  },\r\n],\r\n

# The pattern is: 4-space " },\r\n then 5-space ],
# Should be: 2-space " },\r\n then 2-space ]

BROKEN = b'    " },\r\n     ],'
FIXED = b'  },\r\n],'

pos = raw.find(BROKEN)
print("Broken pattern '\"    },\\r\\n     ],' at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-10:pos+60]))
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
        
        # Show cell structure
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
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found.")
    
    # Let's see what's at byte 166664
    ctx = raw[166654:166720]
    print("\nAround byte 166664:")
    print(' '.join('%02X' % b for b in ctx))
    print(repr(ctx.decode('utf-8', errors='replace')))
