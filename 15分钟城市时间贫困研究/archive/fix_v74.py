NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

line_bytes = raw[line_start:line_end]
print("Current line 3313:")
print("  Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
print("  Text: %s" % repr(line_bytes))

# The line is:     "print('='*60)\n"\",
# Bytes:     20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 22 2C 0A
# Position:  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24
#
# Problem: The string value is: "print('='*60)\n"\",
# It should be:               "print('='*60)\n"\r",
#
# After \n (bytes 19=5C 6E), we have:
#   22 = " (start of next string segment - WRONG!)
#   5C = \ (escape char for \r")
#   22 = " (escaped quote)
#   2C = , (separator)
#
# Should be:
#   22 = " (closing quote for the \n" string)
#   5C = \ (escape for \r)
#   72 = r
#   22 = " (closing quote for \r" string)
#   2C = , (separator)
#
# Fix: Replace the sequence at positions 20-23:
#   From: 22 5C 22 2C  (quote, backslash, quote, comma)
#   To:   22 5C 72 22 2C  (quote, backslash, r, quote, comma)
# i.e., insert 'r' (0x72) between the backslash and quote

# Verify current state
if len(line_bytes) >= 24:
    current = line_bytes[19:24]
    print("\nCurrent bytes 19-23: %s" % ' '.join('%02X' % b for b in current))
    
    # Should be: 5C 6E 22 5C 22 2C
    # Actually:   5C 6E 22 5C 22 2C 0A
    # Position: 18  19  20  21  22  23  24
    print("Position 19: 0x%02X ('%s')" % (line_bytes[19], chr(line_bytes[19])))
    print("Position 20: 0x%02X ('%s')" % (line_bytes[20], chr(line_bytes[20])))
    print("Position 21: 0x%02X ('%s')" % (line_bytes[21], chr(line_bytes[21])))
    print("Position 22: 0x%02X ('%s')" % (line_bytes[22], chr(line_bytes[22])))
    print("Position 23: 0x%02X ('%s')" % (line_bytes[23], chr(line_bytes[23])))
    
    # The fix: insert 0x72 ('r') at position 20
    # So bytes 20-23 become: 72 22 5C 22 2C
    insert_byte = 0x72  # 'r'
    
    # Current: [20]=5C, [21]=22, [22]=2C
    # Target:  [20]=72, [21]=22, [22]=5C, [23]=22, [24]=2C
    
    # Shift bytes 21-23 forward by 1, insert 'r' at position 20
    print("\nFixing: inserting 'r' (0x72) at position %d" % (line_start + 20))
    raw.insert(line_start + 20, insert_byte)
    print("Inserted!")
    
    # Verify
    new_line_start = lf_positions[3311] + 1
    new_line_end = raw.find(b'\n', new_line_start)
    new_line = raw[new_line_start:new_line_end]
    print("\nNew line 3313:")
    print("  Hex: %s" % ' '.join('%02X' % b for b in new_line))
    print("  Text: %s" % repr(new_line))
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("\nSaved.")
    
    try:
        nb = json.loads(raw)
        print("SUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Line too short!")
