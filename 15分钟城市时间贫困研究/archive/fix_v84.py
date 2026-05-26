NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Line 3313 starts at byte 166412 (after LF[3311])
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

print("Line 3313 bytes (%d-%d):" % (line_start, line_end))
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end]))

# The bytes at positions 17-18 in the line are: 22 5C (quote, backslash)
# They should be: 5C 22 (backslash, quote)
# Fix: swap bytes 17 and 18

print("\nBytes 15-22 in line:")
for i in range(15, 23):
    abs_pos = line_start + i
    print("  Line offset %d (byte %d): 0x%02X = '%s'" % (i, abs_pos, raw[abs_pos], chr(raw[abs_pos])))

# Swap bytes at line offsets 17 and 18
byte_17 = raw[line_start + 17]
byte_18 = raw[line_start + 18]
print("\nSwapping:")
print("  Byte %d: 0x%02X ('%s')" % (line_start+17, byte_17, chr(byte_17)))
print("  Byte %d: 0x%02X ('%s')" % (line_start+18, byte_18, chr(byte_18)))

raw[line_start + 17], raw[line_start + 18] = byte_18, byte_17

print("\nAfter swap:")
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end]))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
