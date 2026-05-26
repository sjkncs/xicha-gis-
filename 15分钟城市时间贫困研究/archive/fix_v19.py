NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Show context around the problem area
print("\nLines 3315-3340:")
for i in range(3314, min(3340, len(lines))):
    print("%d: %s" % (i+1, repr(lines[i])))

# The structure should be:
# Line ~: Section 10 cell content "  ]\n",\n    },\n ],
# Line: Section 13 header cell { ... }
# Line: ... cells close ],\n metadata: {

# Let's find where Section 10 should end
# Looking for pattern where a cell closes with "  ],\n" followed by another cell
