NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Try to find and fix structural issues programmatically
with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()

# The issue: JSON parsing fails at line 3313
# Let me trace the JSON structure around that area

# Split into lines
lines = text.split('\n')

# Check lines 3310-3320
print("Lines 3310-3320:")
for i in range(3309, 3320):
    if i < len(lines):
        line = lines[i]
        print("Line %d: %s" % (i+1, repr(line[:100])))
        
# Check the structure:
# Line 3313 should be inside a source array
# After line 3314 (]), the cell object closes
# After line 3315 (}), the cells array should have a comma IF there are more cells

# Let me check if the cells array should be open or closed
# Line 3316: '  ],' - if this closes the cells array
# Then line 3317: '"metadata"' starts the metadata object

# Let me check the cell at lines 3046-3066
# These should be cells in the array
print("\n\nChecking cells around 3046:")
for i in range(3044, 3050):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i][:80])))
        
print("\n\nChecking structure around 3315:")
for i in range(3313, 3320):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i][:80])))
