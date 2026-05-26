NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# The problem: Line 3322 is '    " },' (4 spaces before ")
# It should be '  },' (2 spaces before },)
# The hex is: 22 20 20 20 20 7D 2C
# Should be:   22 20 20 7D 2C

# Search for the broken pattern
BROKEN = b'    " },'
FIXED = b'  " },'

pos = raw.find(BROKEN)
print("Broken '    \" },' pattern at byte: %d" % pos)

if pos >= 0:
    # Show context
    ctx = raw[pos-20:pos+50]
    print("\nContext:")
    print(repr(ctx.decode('utf-8', errors='replace')))
    
    print("\nApplying fix...")
    new_raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved!")
    
    # Verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS: JSON valid! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Still broken: %s at line %d" % (e.msg, e.lineno))
        # Show the problematic area
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found. Let me check the exact bytes...")
    
    # Search for just ' },'
    alt = b' },'
    positions = []
    start = 0
    while True:
        p = raw.find(alt, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
        if len(positions) > 10:
            break
    
    print("Found %d occurrences of ' },'" % len(positions))
    for p in positions:
        ctx = raw[max(0,p-10):p+30]
        print("  byte %d: %s" % (p, repr(ctx.decode('utf-8', errors='replace'))))
