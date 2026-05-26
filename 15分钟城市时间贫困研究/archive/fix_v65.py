NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Current: ...\\r,""
# Should be: ...\\r",
# Fix: Remove one quote

# Find \\r,""
search = b'\\r,"'
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences of \\r,\"" % len(positions))
for p in positions[-5:]:
    print("  byte %d: %s" % (p, repr(raw[p-20:p+30])))

# Find the right one - should be around byte 166433
for p in positions:
    if 166400 < p < 166500:
        print("\nTarget at byte: %d" % p)
        print("Context: %s" % repr(raw[p-30:p+40]))
        
        # Fix: Remove the last "
        new_raw = raw[:p+4] + raw[p+5:]  # Remove one quote
        
        with open(NOTEBOOK_PATH, 'wb') as f:
            f.write(new_raw)
        print("Fixed!")
        
        try:
            with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                nb = json.load(f)
            print("SUCCESS! %d cells" % len(nb['cells']))
        except json.JSONDecodeError as e:
            print("Error: %s at line %d" % (e.msg, e.lineno))
        break
