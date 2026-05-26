NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

lines = text.split('\n')
print("Total lines: %d" % len(lines))

# Check lines around 3314
for i in range(3309, min(3320, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# Check if this is the end of the source array
print("\n=== Checking array structure ===")
# The source array should end with:
#     ],
#    }
# Which means the cell's outputs array closes with ],
# and the cell closes with },

# Line 3314 should be:    ],
# But if it has a comma, that's wrong for closing an array

# Find all ], patterns
import re
matches = list(re.finditer(r'\s+\],', text))
print("\nFound %d '],' patterns" % len(matches))
for m in matches[-5:]:
    pos = m.start()
    print("  Position %d: %s" % (pos, repr(text[pos-20:pos+20])))
