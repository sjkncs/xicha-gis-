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

# Target: "print('='*60)\n"\\r",
# In JSON file bytes: spaces + 22 + print('='*60) + 5C6E + 22 + 5C72 + 22 + 2C
# i.e.: 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C
# That's 25 bytes

# Current: 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 72 22 5C 22 2C
# Target:  20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C

# The problem is at bytes 18-22:
# Current: 5C 6E 72 22 5C (meaning \n r " \)
# Target:  5C 6E 22 5C 72 (meaning \n " \ r)

# Fix: shift bytes 20-22 right by 1 (from 72 22 5C to 22 5C 72)
# and delete the extra byte

# The correct sequence for bytes 18-24 should be:
# [5C, 6E, 22, 5C, 72, 22, 2C] (7 bytes)
# But we have:
# [5C, 6E, 72, 22, 5C, 22, 2C] (7 bytes) -> 8 bytes actually

# Let me count:
# 0-3: spaces (4 bytes)
# 4: 22 (1 byte)
# 5-16: print('='*60) (12 bytes)
# 17: 5C (1 byte)
# 18-?: need to check

print("\nByte analysis:")
for i in range(len(current)):
    print("  %2d: 0x%02X" % (i, current[i]))

# The fix: bytes 20-22 need to be [22, 5C, 72] not [72, 22, 5C]
# So we need to:
# 1. Set byte 20 to 0x22
# 2. Set byte 21 to 0x5C
# 3. Set byte 22 to 0x72
# But byte 18 needs to be 0x6E (it is) and byte 19 needs to be 0x22

# Wait - the current bytes are:
# 17: 5C (correct - start of \n)
# 18: 6E (correct - n in \n)
# 19: 72 (WRONG - should be 22)
# 20: 22 (WRONG - should be 5C)
# 21: 5C (WRONG - should be 72)
# 22: 22 (correct - closing quote)
# 23: 2C (correct - comma)

# So the fix is:
# byte 19: 72 -> 22
# byte 20: 22 -> 5C
# byte 21: 5C -> 72
# OR shift right: byte 21=72, byte 20=5C, byte 19=22

print("\nFixing bytes 19-21...")
# Save byte 22 (0x22) first
b22 = current[22]

# Shift right: 19=20, 20=21, 21=22(b22)
raw[line_start + 19] = raw[line_start + 20]  # 72 -> 22
raw[line_start + 20] = raw[line_start + 21]  # 22 -> 5C
raw[line_start + 21] = b22  # 5C -> 22

current = raw[line_start:line_end]
print("After fix:")
for i in range(len(current)):
    print("  %2d: 0x%02X" % (i, current[i]))

# Verify
target = bytes([0x20,0x20,0x20,0x20, 0x22,0x70,0x72,0x69,0x6E,0x74,0x28,0x27,0x3D,0x27,0x2A,0x36,0x30,0x29,0x5C,0x6E,0x22,0x5C,0x72,0x22,0x2C])
if current == target:
    print("\nMatches target!")
else:
    print("\nStill doesn't match!")
    print("Target: %s" % ' '.join('%02X' % b for b in target))
    for i in range(min(len(current), len(target))):
        if current[i] != target[i]:
            print("  Diff at %d: have 0x%02X, want 0x%02X" % (i, current[i], target[i]))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("\nSaved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
