NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find where the issue is - check around the Fig11 cell
# Look for the pattern: ],  (array close with comma) 

# Search for: ],\r\n or ],\r\r
pos1 = raw.find(b'],\r\n')
pos2 = raw.find(b'],\r\r')
print("Found ],\\r\\n at raw byte %s" % (pos1 if pos1 >= 0 else "not found"))
print("Found ],\\r\\r at raw byte %s" % (pos2 if pos2 >= 0 else "not found"))

# Find the specific area around line 3314
text = raw.decode('utf-8', errors='replace')
lf_positions = [i for i, c in enumerate(text) if c == '\n']

# Line 3314
if len(lf_positions) >= 3313:
    l3314_start = lf_positions[3312] + 1
    l3314_end = lf_positions[3313]
    print("\nLine 3314 bytes (%d-%d):" % (l3314_start, l3314_end))
    print("Bytes: %s" % ' '.join('%02X' % b for b in raw[l3314_start:l3314_end]))
    
    # Check if it ends with ], or just ]
    line_bytes = raw[l3314_start:l3314_end]
    print("Ends with: %s" % ' '.join('%02X' % b for b in line_bytes[-5:]))
    
    # The issue: it has ], but should have ]

# Let me find ALL ], patterns in raw bytes
import re
matches = list(re.finditer(b'\\],', raw))
print("\nFound %d '],' patterns in raw bytes" % len(matches))
for m in matches[-5:]:
    pos = m.start()
    print("  Position %d: %s" % (pos, ' '.join('%02X' % b for b in raw[pos:pos+10])))
