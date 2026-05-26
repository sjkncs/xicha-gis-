NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The raw bytes at position 149444-149470 should be line 3313
# But they show incomplete content
# Let me search for the COMPLETE print statement in raw bytes

# Search for: print('='*60)\n"\
search = b"print('='*60)"
positions = []
start = 0
while True:
    pos = raw.find(search, start)
    if pos < 0:
        break
    positions.append(pos)
    start = pos + 1

print("Found %d occurrences of print('='*60)" % len(positions))
for p in positions:
    print("  Raw byte %d: %s" % (p, ' '.join('%02X' % b for b in raw[p:p+30])))
    # Decode this
    try:
        chunk = raw[p-5:p+25].decode('utf-8', errors='replace')
        print("  Decoded: %s" % repr(chunk))
    except:
        pass

# Find ALL occurrences of \\n in the raw bytes (5C 6E)
# This might help us find the actual line boundaries
print("\n=== Searching for complete string pattern ===")
# Search for: "    "print('='*60
search2 = b'"    "print(\'=\''
pos2 = raw.find(search2)
if pos2 >= 0:
    print("Found '\"    \"print(\\'=\\'...' at raw byte %d" % pos2)
    print("Context (50 bytes): %s" % ' '.join('%02X' % b for b in raw[pos2:pos2+50]))
    # Find the closing quote and newline
    # Looking for: ...)\n", 
    # = 29 5C 6E 22 2C
