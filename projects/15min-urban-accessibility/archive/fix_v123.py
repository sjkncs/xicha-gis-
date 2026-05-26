NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check lines around 3313
lines = text.split('\n')
print("Total lines: %d" % len(lines))

# Check lines 3310-3315
for i in range(3309, min(3316, len(lines))):
    line = lines[i]
    print("Line %d: %s" % (i+1, repr(line)))

# Check the last few lines of the file
print("\n=== Last 10 lines ===")
for i in range(max(0, len(lines)-10), len(lines)):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))
