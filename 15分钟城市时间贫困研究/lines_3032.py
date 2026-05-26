NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Get exact lines around 3032
text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("Lines 3028-3340:")
for i in range(3027, min(3340, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))
