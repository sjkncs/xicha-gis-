NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

# The line should be:     "print('='*60)\n"\\r",
# i.e., JSON string: "print(\'=\'*60)\\n\"\\r\",\r\n"
# Bytes: 
# 0-3: 20 20 20 20  (4 spaces)
# 4: 22 ('"')
# 5-16: print('='*60)  (12 chars)
# 17: 5C ('\')
# 18: 6E ('n')
# 19: 22 ('"')
# 20: 5C ('\')
# 21: 72 ('r')
# 22: 22 ('"')
# 23: 2C (',')
# 24: 0D (CR)
# 25: 0A (LF)

# Target bytes for the meaningful part (0-23):
target = b'    "print(\'=\'*60)\\n"\\r",'
# = 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C

print("Current bytes (first 26):")
current = raw[line_start:line_end+1]
for i in range(min(26, len(current))):
    print("  Byte %d: 0x%02X = '%s'" % (i, current[i], chr(current[i]) if 32 <= current[i] < 127 else '?'))

print("\nTarget bytes:")
for i in range(len(target)):
    print("  Byte %d: 0x%02X = '%s'" % (i, target[i], chr(target[i]) if 32 <= target[i] < 127 else '?'))

print("\nDifferences:")
for i in range(min(len(current), len(target))):
    if i < len(current) and i < len(target) and current[i] != target[i]:
        print("  Line offset %d: have 0x%02X ('%s'), want 0x%02X ('%s')" % (
            i, current[i], chr(current[i]) if 32 <= current[i] < 127 else '?',
            target[i], chr(target[i]) if 32 <= target[i] < 127 else '?'))
if len(current) != len(target):
    print("  Length: have %d, want %d" % (len(current), len(target)))

# Fix by overwriting the problematic bytes (20-22)
# Current at 20-22: 22 5C 72 (" \ r)
# Target at 20-22: 5C 72 22 (\ r ")
# So we need to change: 22 -> 5C at position 20
#                        5C -> 72 at position 21
#                        72 -> 22 at position 22
print("\nFixing bytes 20-22...")
raw[line_start + 20] = 0x5C  # was 0x22
raw[line_start + 21] = 0x72  # was 0x5C
raw[line_start + 22] = 0x22  # was 0x72

# Verify
current = raw[line_start:line_end+1]
print("\nAfter fix:")
for i in range(min(26, len(current))):
    print("  Byte %d: 0x%02X = '%s'" % (i, current[i], chr(current[i]) if 32 <= current[i] < 127 else '?'))

# Verify matches target
match = True
for i in range(len(target)):
    if i < len(current) and current[i] != target[i]:
        print("Mismatch at byte %d" % i)
        match = False
        break
if match:
    print("\nLine now matches target!")

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
