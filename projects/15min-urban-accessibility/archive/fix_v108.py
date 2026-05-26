NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find all occurrences of road_network in the file
road_positions = []
start = 0
while True:
    pos = text.find('road_network', start)
    if pos < 0:
        break
    road_positions.append(pos)
    start = pos + 1

print("Found %d occurrences of 'road_network'" % len(road_positions))
for pos in road_positions:
    print("  Text pos %d: %s" % (pos, repr(text[pos-30:pos+50])))

# Check what cell contains road_network
print("\n=== Checking cells ===")
cell_count = text.count('"cell_type"')
print("Total cells: %d" % cell_count)

# Check around line 3312
lines = text.split('\n')
print("\n=== Lines 3300-3330 ===")
for i in range(3299, 3330):
    line = lines[i] if i < len(lines) else ""
    if 'road_network' in line or 'Fig11' in line:
        print("Line %d: %s" % (i+1, repr(line[:100])))
