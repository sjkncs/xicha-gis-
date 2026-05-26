NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

lines = text.split('\n')
print("Total lines: %d" % len(lines))

# Check lines around 3314
for i in range(3309, 3320):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i])))

# Find all "outputs": [] patterns
print("\n=== All outputs: [] patterns ===")
import re
matches = list(re.finditer(r'"outputs": \[]', text))
print("Found %d '\"outputs\": []' patterns" % len(matches))
for m in matches:
    pos = m.start()
    line_num = text[:pos].count('\n') + 1
    print("  Line %d: %s" % (line_num, repr(text[pos:pos+30])))
