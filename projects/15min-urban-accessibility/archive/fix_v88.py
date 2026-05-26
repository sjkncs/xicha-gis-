NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

current = raw[line_start:line_end]
print("Current line 3313 (%d-%d, %d bytes):" % (line_start, line_end, len(current)))
print("Hex: %s" % ' '.join('%02X' % b for b in current))

# Target: "print(\'=\'*60)\\n"\\r",
# Bytes:
# 0-3:   20 20 20 20
# 4:      22 (")
# 5-16:   70 72 69 6E 74 28 27 3D 27 2A 36 30 29  (print('='*60))
# 17:     5C (\)
# 18:     6E (n)
# 19:     22 (")
# 20:     5C (\)
# 21:     72 (r)
# 22:     22 (")
# 23:     2C (,)

target = b'    "print(\'=\'*60)\\n"\\r",'
print("\nTarget (%d bytes):" % len(target))
print("Hex: %s" % ' '.join('%02X' % b for b in target))

print("\nDifferences:")
for i in range(min(len(current), len(target))):
    if current[i] != target[i]:
        print("  Line offset %d: have 0x%02X ('%s'), want 0x%02X ('%s')" % (
            i, current[i], chr(current[i]) if 32 <= current[i] < 127 else '?',
            target[i], chr(target[i]) if 32 <= target[i] < 127 else '?'))
if len(current) != len(target):
    print("  Length: have %d, want %d" % (len(current), len(target)))

# Fix: overwrite with target bytes
print("\nOverwriting line with target bytes...")
raw[line_start:line_end] = target

# Verify
current = raw[line_start:line_start+len(target)]
print("After fix (%d bytes):" % len(current))
print("Hex: %s" % ' '.join('%02X' % b for b in current))

if current == target:
    print("Line matches target!")
else:
    print("Still doesn't match!")

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
