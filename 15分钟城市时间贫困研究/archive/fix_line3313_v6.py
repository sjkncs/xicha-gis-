NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Check the actual raw bytes of line 3313
# Find where line 3313 starts and ends

# Count LF to find line boundaries
lf_positions = []
for i, b in enumerate(raw):
    if b == 0x0A:
        lf_positions.append(i)

print("Total LF: %d" % len(lf_positions))

# Line 3313 starts after LF 3312 (index 3312)
# Line 3313 ends at LF 3312
if len(lf_positions) >= 3313:
    line_start = lf_positions[3311] + 1  # after LF 3312
    line_end = lf_positions[3312]  # at LF 3313
    
    print("Line 3313 bytes: %d to %d" % (line_start, line_end))
    
    line_bytes = raw[line_start:line_end]
    print("Length: %d bytes" % len(line_bytes))
    print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
    print("Text: %s" % line_bytes.decode('utf-8', errors='replace'))
    
    # Check if there's a trailing comma
    if line_bytes.endswith(b','):
        print("Ends with COMMA - might be wrong for last element")
    elif line_bytes.endswith(b'\\r"'):
        print("Ends with escaped CR and quote")
    else:
        print("Ends with: %s" % repr(line_bytes[-10:]))
