NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# ANALYSIS: The Section 10 cell has a source array starting at line 3327
# Line 3327: '    "  \"source\": ['  <- source array opening
# Lines 3328-3390+: corrupted Section 13 code (inside source array)
# Lines around 3390-3400: likely close of source array + close of cell
# Line 3398: Section 9 markdown starts
# ================================================================

# Show lines around 3380-3410 to find the source array closing
print("\n=== Lines 3375 to 3410 ===")
for i in range(3374, min(3410, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# Also show the full source array structure around lines 3326-3330
print("\n=== Section 10 source array start ===")
for i in range(3325, 3335):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# Find the Section 10 cell closing
# Look for patterns like: ],  },  { (next cell opens)
print("\n=== Looking for Section 10 cell close ===")
for i in range(3380, 3400):
    l = lines[i].strip()
    if l in [']', '],', '},', '},', '}', '],']:
        print("Line %d: %s (matched pattern '%s')" % (i+1, repr(lines[i]), l))
    else:
        print("Line %d: %s" % (i+1, repr(lines[i][:80])))
