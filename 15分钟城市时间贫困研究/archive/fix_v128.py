NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Try to read the file in different ways
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Method 1: Try json.load with text mode
print("=== Method 1: json.load with text mode ===")
try:
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))

# Method 2: Try json.loads with raw bytes
print("\n=== Method 2: json.loads with raw bytes ===")
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))

# Method 3: Check if there's a trailing comma issue
# Look for pattern: ,] which is a trailing comma
print("\n=== Checking for trailing commas ===")
text = raw.decode('utf-8', errors='replace')

# Find all ,] patterns
import re
matches = list(re.finditer(r',\s*\]', text))
print("Found %d trailing comma patterns" % len(matches))
for m in matches[-10:]:  # Show last 10
    pos = m.start()
    print("  Position %d: %s" % (pos, repr(text[pos-10:pos+10])))

# Check around line 3313
print("\n=== Checking lines 3310-3315 ===")
lines = text.split('\n')
for i in range(3309, min(3316, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:80])))
