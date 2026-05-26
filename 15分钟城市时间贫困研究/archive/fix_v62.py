NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# From the analysis:
# At byte 166434, we have 'p' (the start of print('='*60))
# But it should have a quote before it: "print('='*60)
# Current: space, space, space, p
# Fix: space, space, space, ", p

# Find the pattern: 4 spaces followed by p (of print)
search = bytes([0x20, 0x20, 0x20, 0x20, 0x70])  # 4 spaces + p
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences of 4 spaces + 'p'" % len(positions))
for p in positions:
    # Check what comes after 'p'
    if p + 8 < len(raw):
        after_p = raw[p+4:p+12]
        print("  byte %d: %s" % (p, repr(after_p)))

# The 4th occurrence should be the problematic one (line 3313)
if len(positions) >= 4:
    target = positions[3]  # 4th occurrence (0-indexed)
    print("\nTarget at byte: %d" % target)
    print("Context: %s" % repr(raw[target-10:target+30]))
    
    # Check if there's already a quote before 'p'
    if target > 0 and raw[target-1] == 0x22:
        print("Quote already exists!")
    else:
        # Insert quote
        new_raw = raw[:target] + b'"' + raw[target:]
        
        with open(NOTEBOOK_PATH, 'wb') as f:
            f.write(new_raw)
        print("Fixed! Inserted quote before print")
        
        # Verify
        try:
            with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                nb = json.load(f)
            print("SUCCESS! %d cells" % len(nb['cells']))
            
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
