NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

print("Line 3313 bytes (%d-%d):" % (line_start, line_end))
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end]))

# The bytes should be:
# Spaces + "print('='*60)\\n"\\r",\\r\\n"
# i.e., 25 bytes + CR + LF = 27 bytes total
# 
# Current (25 bytes): 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C
# Should be (25 bytes): 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C
# -> They're the SAME!

# But then what about CR and LF?
print("\nByte after line_end (%d): 0x%02X" % (line_end, raw[line_end] if line_end < len(raw) else None))

# Ah! The line_end is at LF (0x0A)
# The byte BEFORE that (line_end - 1) should be CR (0x0D) or the closing quote
# Let's check
print("Byte at line_end-1 (%d): 0x%02X" % (line_end-1, raw[line_end-1]))
print("Byte at line_end (%d): 0x%02X" % (line_end, raw[line_end]))

# Show the last 5 bytes of the line
print("\nLast 5 bytes of line:")
for i in range(max(line_start, line_end-5), line_end):
    print("  Byte %d: 0x%02X" % (i, raw[i]))

# So: the line ends with: 2C 0A (comma, LF)
# But it SHOULD end with: 2C 0D 0A (comma, CR, LF)

# FIX: Insert CR (0x0D) before the LF at line_end
print("\nInserting CR (0x0D) at byte %d..." % line_end)
raw.insert(line_end, 0x0D)
print("Inserted!")

# Verify
print("\nNew last 5 bytes:")
for i in range(max(line_start, line_end-5), line_end+1):
    print("  Byte %d: 0x%02X" % (i, raw[i]))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("\nSaved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
