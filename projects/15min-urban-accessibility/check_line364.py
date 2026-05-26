NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.read().split('\n')

# Check lines 360-370
print("Lines 360-370:")
for i in range(359, 370):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i][:120])))
