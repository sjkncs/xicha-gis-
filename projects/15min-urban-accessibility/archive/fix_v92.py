NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

current = raw[line_start:line_end]
print("Current line 3313 (%d bytes):" % len(current))
print("Hex: %s" % ' '.join('%02X' % b for b in current))
print("Chars: %s" % repr(bytes(current)))

# The bytes at positions 20-22 are wrong:
# Current: 72 22 5C = 'r' '"' '\'
# Should be: 22 5C 72 = '"' '\' 'r'
# This gives: " \" r " = \"\\r"

print("\nByte 20: 0x%02X ('%s')" % (raw[line_start+20], chr(raw[line_start+20])))
print("Byte 21: 0x%02X ('%s')" % (raw[line_start+21], chr(raw[line_start+21])))
print("Byte 22: 0x%02X ('%s')" % (raw[line_start+22], chr(raw[line_start+22])))

# Fix: rotate right (0x72 -> 0x22, 0x22 -> 0x5C, 0x5C -> 0x72)
b20 = raw[line_start + 20]  # 0x72
b21 = raw[line_start + 21]  # 0x22
b22 = raw[line_start + 22]  # 0x5C

print("\nRotating: [0x%02X, 0x%02X, 0x%02X] -> [0x%02X, 0x%02X, 0x%02X]" % (
    b20, b21, b22,
    b21, b22, b20
))

raw[line_start + 20] = b21  # 0x22
raw[line_start + 21] = b22  # 0x5C
raw[line_start + 22] = b20  # 0x72

current = raw[line_start:line_end]
print("\nAfter fix:")
print("Hex: %s" % ' '.join('%02X' % b for b in current))

# Should be: 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C
# i.e., spaces + " + print('='*60) + \ + n + " + \ + r + " + ,
target = bytes([0x20,0x20,0x20,0x20, 0x22,0x70,0x72,0x69,0x6E,0x74,0x28,0x27,0x3D,0x27,0x2A,0x36,0x30,0x29,0x5C,0x6E,0x22,0x5C,0x72,0x22,0x2C])
if current == target:
    print("Matches target!")
else:
    print("Still doesn't match!")
    print("Target: %s" % ' '.join('%02X' % b for b in target))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("\nSaved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
