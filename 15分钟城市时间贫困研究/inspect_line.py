NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find line 3348 (idx 3347)
lines = content.split('\n')
line = lines[3347]  # 0-indexed

print("Line 3348 (idx 3347):")
print(repr(line))
print("\nLength:", len(line))
print("\nChar-by-char analysis:")

# Split by " to see structure
parts = line.split('"')
print("\nSplit by double-quote (%d parts):" % len(parts))
for i, p in enumerate(parts[:15]):
    print("  part[%d]: %s" % (i, repr(p)))
