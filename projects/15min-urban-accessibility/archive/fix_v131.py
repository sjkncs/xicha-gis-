NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find line 3314 in raw bytes
lf_positions = [i for i, c in enumerate(text) if c == '\n']
print("Total LFs: %d" % len(lf_positions))

# Line 3314 starts after LF[3312], ends at LF[3313]
l3314_start = lf_positions[3312] + 1
l3314_end = lf_positions[3313]
print("Line 3314 bytes (%d-%d):" % (l3314_start, l3314_end))
line_bytes = raw[l3314_start:l3314_end]
print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))

# Also check the full context around the area
print("\n=== Context bytes 149440-149500 ===")
for i in range(149440, 149500, 10):
    chunk = raw[i:i+10]
    print("%d: %s" % (i, ' '.join('%02X' % b for b in chunk)))

# Find all ], patterns in the file
print("\n=== Finding all ], patterns ===")
import re
matches = list(re.finditer(r'\],', text))
print("Found %d '],' patterns" % len(matches))
for i, m in enumerate(matches):
    pos = m.start()
    line_num = text[:pos].count('\n') + 1
    print("  #%d at position %d (line %d): %s" % (i+1, pos, line_num, repr(text[pos-10:pos+20])))
