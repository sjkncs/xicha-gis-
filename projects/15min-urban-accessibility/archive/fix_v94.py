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

# Target line: "print('='*60)\\n"\\r",
# Bytes:
# 0-3:   spaces (4 bytes)
# 4:      22 (")
# 5-16:   print('='*60) (12 bytes)
# 17:     5C (\)
# 18:     6E (n)
# 19:     22 (")
# 20:     5C (\)
# 21:     72 (r)
# 22:     22 (")
# 23:     2C (,)
# 24:     0D (CR)
# 25:     0A (LF)

# Current line has 25 bytes (no CR), but bytes 18-22 are wrong:
# Current bytes 18-22: 29 6E 72 22 5C (should be: 6E 22 5C 72 22)
# That's: \) n r " \
# Should be:           n " \ r "

# The sequence 29 6E 72 22 5C should become 6E 22 5C 72 22
# i.e., bytes 19-22 shift left by 2 positions, overwriting bytes 18-19

print("\nFixing: shifting bytes 19-22 left by 2 positions...")
print("Before: bytes 18-22 = %s" % ' '.join('%02X' % b for b in current[18:23]))

# Shift left by 2: byte[19] -> byte[17], byte[20] -> byte[18], byte[21] -> byte[19], byte[22] -> byte[20]
# Save bytes 19-22 first
b19 = current[19]  # 0x72
b20 = current[20]  # 0x22
b21 = current[21]  # 0x5C
b22 = current[22]  # 0x72

# Now shift
raw[line_start + 18] = b20  # 0x22 (was at 20)
raw[line_start + 19] = b21  # 0x5C (was at 21)
raw[line_start + 20] = b22  # 0x72 (was at 22)
raw[line_start + 21] = 0x22  # 0x22
raw[line_start + 22] = 0x2C  # 0x2C

# Also add CR before LF
# The line currently ends at line_end with just LF (0x0A)
# We need CR (0x0D) before it
print("\nAdding CR before LF...")
raw.insert(line_end, 0x0D)

# Verify
current = raw[line_start:line_start+27]
print("\nAfter fix (27 bytes):")
print("Hex: %s" % ' '.join('%02X' % b for b in current))

# Target
target = bytes([0x20,0x20,0x20,0x20, 0x22,0x70,0x72,0x69,0x6E,0x74,0x28,0x27,0x3D,0x27,0x2A,0x36,0x30,0x29,0x5C,0x6E,0x22,0x5C,0x72,0x22,0x2C,0x0D,0x0A])
print("\nTarget (27 bytes):")
print("Hex: %s" % ' '.join('%02X' % b for b in target))

if current == target:
    print("\nMatches target!")
else:
    print("\nDoesn't match")
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
