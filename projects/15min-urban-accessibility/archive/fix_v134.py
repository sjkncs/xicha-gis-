NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

lines = text.split('\n')
print("Total lines: %d" % len(lines))

# Check lines 130-140
for i in range(129, min(140, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# Check around the area I modified
print("\n=== Context around position 166438 ===")
print("Text around 166438: %s" % repr(text[166400:166500]))
