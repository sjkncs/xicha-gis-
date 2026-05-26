NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Search for Section 13 mentions
print("=== Searching for Section 13 ===")
for i, line in enumerate(lines):
    if 'Section 13' in line or '第13' in line or 'section_13' in line.lower():
        print("Line %d: %s" % (i+1, repr(line.strip()[:100])))

# Search for Claude API mentions (these would be in Section 13)
print("\n=== Searching for Claude API ===")
for i, line in enumerate(lines):
    if 'Claude' in line or 'claude' in line or 'ANTHROPIC_API' in line:
        print("Line %d: %s" % (i+1, repr(line.strip()[:100])))

# Search for street view mentions
print("\n=== Searching for street view ===")
for i, line in enumerate(lines):
    if 'street_view' in line or 'StreetView' in line or 'gaode' in line.lower() or '高德' in line:
        print("Line %d: %s" % (i+1, repr(line.strip()[:100])))

# Check the first cell content
print("\n=== First cell content ===")
for i in range(0, 50):
    print("Line %d: %s" % (i+1, repr(lines[i][:80])))

# Check around line 8 where Section 13 markdown should be
print("\n=== Lines 7-10 ===")
for i in range(6, 10):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))
