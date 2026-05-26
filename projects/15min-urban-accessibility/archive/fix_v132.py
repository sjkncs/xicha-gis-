NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the file
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Let me manually trace through the JSON structure to find trailing commas
# Looking for patterns like: "],\n  },\n  ]\n" where the first ], is trailing

# Find the pattern: comma before ] in the outputs/source array context
print("=== Looking for trailing comma patterns ===")

# Look for: ], followed by } (array close followed by object close)
import re

# Pattern: ] followed by comma (],) before end of object
# This is valid in some JSON but not standard
matches = list(re.finditer(r'\],\s*}', text))
print("Found %d '], }' patterns" % len(matches))
for m in matches[-5:]:
    pos = m.start()
    line_num = text[:pos].count('\n') + 1
    print("  Line %d: %s" % (line_num, repr(text[pos:pos+30])))

# Find all ], patterns that close arrays
# Check if any ], is inside a source array and should just be ]
matches2 = list(re.finditer(r'\],\n', text))
print("\nFound %d '],\n' patterns" % len(matches2))
for i, m in enumerate(matches2[-10:]):
    pos = m.start()
    line_num = text[:pos].count('\n') + 1
    # Check context before
    before = text[max(0,pos-50):pos]
    print("  Line %d: ...%s" % (line_num, repr(before[-30:]) + repr(text[pos:pos+20])))

# Let me try to manually parse just the cell containing Fig11
print("\n=== Checking cell structure ===")
# Find the Fig11 cell
fig11_pos = text.find('Fig11')
if fig11_pos >= 0:
    line_num = text[:fig11_pos].count('\n') + 1
    print("Fig11 at line %d" % line_num)
