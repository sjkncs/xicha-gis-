NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Show context around the problem - look backwards from line 3315
print("\nLines 3300-3325:")
for i in range(3299, 3325):
    print("%d: %s" % (i+1, repr(lines[i])))

# The issue is: 
# - Line 3314 has `    "  ]\n",` which closes a source array
# - Line 3315 has `  " },\n",` which closes a cell object  
# But there should be another `],` to close the cells array
# - Line 3323 has ` ],` which is supposed to close cells array

# But actually looking at line 3314 more carefully:
# Line 3314: `    "  ]\n",` - this is a source array close
# Line 3315: `  " },\n",` - this is a cell object close (4-space indent, not 2-space!)
# Line 3316: `    " {\n",` - this is wrong, should be another cell start

# The fix: 
# 1. Close the source array at line 3314: `    "  ]\n",` - this is correct
# 2. Close the cell object at line 3315: change `  " },\n",` to `  },\n`,  - WRONG indentation
#    Actually, looking at the JSON error at line 3322, the issue is that:
#    - The Section 13 content is INSIDE a source array of some cell
#    - Line 3314 is `    "  ]\n",` which closes a source array
#    - Lines 3315-3322 should be a complete cell, but they're malformed

# Let me check what cell this source array belongs to
# Search for where the source array started
print("\n\nSearching for source array open before line 3314...")
for i in range(3313, -1, -1):
    if '"source": [' in lines[i] or "'source': [" in lines[i]:
        print("Line %d: %s" % (i+1, repr(lines[i])))
        print("Context (next 5 lines):")
        for j in range(i, min(i+10, len(lines))):
            print("  %d: %s" % (j+1, repr(lines[j])))
        break
