NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Look at Section 10 cell around lines 3300-3335
print("\n=== Section 10 cell context (lines 3290-3335) ===")
for i in range(3289, min(3335, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# Show bytes around char 146520 (error position)
print("\n=== Bytes around char 146520 ===")
chunk = content[146480:146580]
print(repr(chunk))

# Try parsing the whole file as JSON and see what happens
print("\n=== Trying full JSON parse ===")
try:
    nb = json.loads(content)
    print("Valid JSON! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at char %d" % (e, e.pos))
    ln = content[:e.pos].count('\n') + 1
    print("Line %d: %s" % (ln, repr(content.split('\n')[ln-1][:100])))
