NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("File structure (first and last 50 lines):")
print("=" * 60)
for i in range(min(50, len(lines))):
    print("Line %d: %s" % (i+1, lines[i][:100]))
    
print("\n...\n")

for i in range(max(0, len(lines)-50), len(lines)):
    print("Line %d: %s" % (i+1, lines[i][:100]))

print("\n" + "=" * 60)
print("Total lines: %d" % len(lines))

# Check indentation of key lines
print("\n\nChecking indentation of closing brackets:")
for i in [3043, 3044, 3045, 3046, 3314, 3315, 3316]:
    if i < len(lines):
        line = lines[i]
        spaces = len(line) - len(line.lstrip())
        print("Line %d (spaces=%d): %s" % (i+1, spaces, repr(line[:50])))
