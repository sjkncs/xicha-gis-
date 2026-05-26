NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The problem: after \\r we have "" (two quotes) instead of " (one quote)
# This means the line has: \\r"", followed by comma
# It should be: \\r",  followed by comma (one quote)

# Search for the pattern in the file
# The bytes we want to fix are around the print('='*60) statement
# Current: 5C 6E 72 22 22 2C (meaning \n r " " ,)
# Target:  5C 6E 72 22 2C         (meaning \n r " ,)

# Search for: \n\r"",
search = b'\\n\\r"",'
replace = b'\\n\\r",'

positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences of \\n\\r\"\"," % len(positions))
for p in positions:
    print("  Byte %d: %s" % (p, repr(raw[p-20:p+30])))

if positions:
    # Fix the last occurrence (the one near line 3313)
    p = positions[-1]
    print("\nFixing at byte %d" % p)
    
    # Show what's there
    print("Before: %s" % repr(raw[p:p+20]))
    
    # Replace: remove one quote (from "" to ")
    raw[p+5:p+6] = b''  # Remove the second quote (byte after \\r")
    
    print("After:  %s" % repr(raw[p:p+20]))
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("Saved.")
    
    # Verify
    try:
        nb = json.loads(raw)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found - trying alternative search...")
    
    # Alternative: search for \\r"",
    alt_search = b'\\r"",'
    alt_positions = []
    start = 0
    while True:
        p = raw.find(alt_search, start)
        if p < 0:
            break
        alt_positions.append(p)
        start = p + 1
    
    print("Found %d occurrences of \\r\"\"," % len(alt_positions))
    for p in alt_positions:
        print("  Byte %d: %s" % (p, repr(raw[p-20:p+30])))
