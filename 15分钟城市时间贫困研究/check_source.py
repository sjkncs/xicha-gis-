NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# The source array starts at line 3072
# Let's see how many lines are in it
source_start = 3071  # 0-indexed

# Find the source close ] by counting brackets
# Each source line starts with 4 spaces + quote, ends with ",\n or "\n
# We need to find the matching ]

# Let's look at lines around 3200-3300 to see if there's corruption
print("Lines 3195-3210:")
for i in range(3194, 3210):
    print("%d: %s" % (i+1, repr(lines[i])))

# Let's also check if there's any stray '],\n' before line 3314
print("\n\nSearching for '],\n' between 3100 and 3314...")
for i in range(3100, 3314):
    if lines[i].strip() == '],':
        print("Line %d: %s" % (i+1, repr(lines[i])))
