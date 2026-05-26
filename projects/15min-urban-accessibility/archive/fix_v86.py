NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1

# Current bytes at positions 20-22:
# Position 20: 0x72 ('r')
# Position 21: 0x22 ('"')
# Position 22: 0x5C ('\')

# Should be:
# Position 20: 0x22 ('"')
# Position 21: 0x5C ('\')
# Position 22: 0x72 ('r')

# Rotate right: [r, ", \] → ["\, r]
pos_20 = raw[line_start + 20]
pos_21 = raw[line_start + 21]
pos_22 = raw[line_start + 22]

print("Before:")
print("  Byte %d: 0x%02X ('%s')" % (line_start+20, pos_20, chr(pos_20)))
print("  Byte %d: 0x%02X ('%s')" % (line_start+21, pos_21, chr(pos_21)))
print("  Byte %d: 0x%02X ('%s')" % (line_start+22, pos_22, chr(pos_22)))

# Fix: rotate right
# New 20 = old 21
# New 21 = old 22
# New 22 = old 20
raw[line_start + 20] = pos_21  # 0x22
raw[line_start + 21] = pos_22  # 0x5C
raw[line_start + 22] = pos_20  # 0x72

print("\nAfter:")
print("  Byte %d: 0x%02X ('%s')" % (line_start+20, raw[line_start+20], chr(raw[line_start+20])))
print("  Byte %d: 0x%02X ('%s')" % (line_start+21, raw[line_start+21], chr(raw[line_start+21])))
print("  Byte %d: 0x%02X ('%s')" % (line_start+22, raw[line_start+22], chr(raw[line_start+22])))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("\nSaved.")

# Verify
try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
