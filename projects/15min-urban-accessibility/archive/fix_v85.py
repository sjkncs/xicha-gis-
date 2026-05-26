NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

print("Current line 3313 (%d-%d):" % (line_start, line_end))
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end]))
print("Length: %d bytes" % (line_end - line_start))

# Show each byte with position
print("\nByte-by-byte:")
for i in range(line_end - line_start):
    abs_pos = line_start + i
    print("  Line %d (byte %d): 0x%02X = '%s'" % (i, abs_pos, raw[abs_pos], chr(raw[abs_pos]) if 32 <= raw[abs_pos] < 127 else '?'))

# UNDO the swap: swap bytes 17 and 18 back
byte_17 = raw[line_start + 17]
byte_18 = raw[line_start + 18]
print("\nUndoing swap: swapping bytes 17 and 18 back")
raw[line_start + 17], raw[line_start + 18] = byte_18, byte_17

print("After undo:")
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end]))

# The CORRECT line should be:
# print('='*60)\n\r",
# i.e., bytes: print('='*60) \n " \r ",
# In JSON: "print(\'=\'*60)\\n\"\\r\","
# Bytes: 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C

# Let me verify what we have and what we need
print("\n=== Current vs Expected ===")
current = raw[line_start:line_end]
# What the bytes SHOULD be for "print(\'=\'*60)\\n\"\\r\",":
expected_bytes = b'    "print(\'=\'*60)\\n"\\r",'

print("Current length: %d" % len(current))
print("Expected length: %d" % len(expected_bytes))

print("\nCurrent: %s" % ' '.join('%02X' % b for b in current))
print("Expected: %s" % ' '.join('%02X' % b for b in expected_bytes))

# Find the differences
for i in range(min(len(current), len(expected_bytes))):
    if current[i] != expected_bytes[i]:
        print("Diff at byte %d: have 0x%02X, want 0x%02X" % (i, current[i], expected_bytes[i]))
if len(current) != len(expected_bytes):
    print("Length mismatch!")
