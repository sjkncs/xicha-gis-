NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Print the full context around the problem area
print("\n=== Lines 3340 to 3360 ===")
for i in range(3339, min(3360, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# Find what Section 10's source array looks like now
print("\n=== Section 10 source array end ===")
print("Line 3327:", repr(lines[3326][:80]))
print("Line 3328:", repr(lines[3327][:80]))
print("Line 3329:", repr(lines[3328][:80]))
print("Line 3330:", repr(lines[3329][:80]))
print("Line 3331:", repr(lines[3330][:80]))

# Check Section 9
print("\n=== Section 9 start ===")
sec9_idx = None
for i, l in enumerate(lines):
    if "<a id='9'>" in l or "id='9'" in l or "id=\"9\"" in l:
        print("Found Section 9 at line %d: %s" % (i+1, repr(l[:80])))
        sec9_idx = i
        break

# Also search for closing structure
print("\n=== Searching for cell closing patterns ===")
for i in range(3320, 3345):
    l = lines[i].strip()
    if l in [']', '},', '},', '}', '],']:
        print("Line %d: %s" % (i+1, repr(lines[i])))
