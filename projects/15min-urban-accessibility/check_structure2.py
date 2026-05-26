NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("Lines 3310-3331:")
for i in range(3309, 3331):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i][:100])))
        
print("\n\nLet me check for issues around lines 3040-3060:")
# Find where Section 9/10 markdown is
for i in range(3040, 3070):
    if i < len(lines):
        line = lines[i]
        if '"cell_type"' in line or '"markdown"' in line or 'Section 9' in line or 'Section 10' in line or 'cell_type' in line:
            print("Line %d: %s" % (i+1, repr(line[:100])))
