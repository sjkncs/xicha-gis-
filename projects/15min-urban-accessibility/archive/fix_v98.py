NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find where line 3312 and 3313 really start
# Using raw LF positions
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_3312_start = lf_positions[3311] + 1
line_3312_end = lf_positions[3312]
line_3313_start = lf_positions[3312] + 1
line_3313_end = lf_positions[3313] if len(lf_positions) > 3313 else len(raw)

print("Line 3312: bytes %d to %d (%d bytes)" % (line_3312_start, line_3312_end, line_3312_end - line_3312_start))
print("Line 3313: bytes %d to %d (%d bytes)" % (line_3313_start, line_3313_end, line_3313_end - line_3313_start))

line_3312_bytes = raw[line_3312_start:line_3312_end]
line_3313_bytes = raw[line_3313_start:line_3313_end]

print("\nLine 3312 raw bytes:")
print("  Hex: %s" % ' '.join('%02X' % b for b in line_3312_bytes))
print("  Text: %s" % repr(line_3312_bytes))

print("\nLine 3313 raw bytes:")
print("  Hex: %s" % ' '.join('%02X' % b for b in line_3313_bytes))
print("  Text: %s" % repr(line_3313_bytes))

# Check what's before line 3312
print("\n=== Content before line 3312 ===")
for i in range(3311, max(3300, 3311-15), -1):
    lf_start = lf_positions[i-1] + 1 if i > 0 else 0
    lf_end = lf_positions[i]
    line_bytes = raw[lf_start:lf_end]
    print("Line %d (bytes %d-%d): %s" % (i+1, lf_start, lf_end, repr(line_bytes)))
