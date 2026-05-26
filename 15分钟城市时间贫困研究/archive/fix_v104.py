NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The issue: byte 166429 is 0x5C (\) but should be 0x29 ()
# This is the closing parenthesis of print('='*60)

print("Before fix:")
print("  Byte 166429: 0x%02X = '%s'" % (raw[166429], chr(raw[166429])))

# Fix byte 166429: change \ (0x5C) to ) (0x29)
raw[166429] = 0x29

print("After fix:")
print("  Byte 166429: 0x%02X = '%s'" % (raw[166429], chr(raw[166429])))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Show the corrected line
    lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
    line_start = lf_positions[3311] + 1
    line_end = lf_positions[3312]
    line = raw[line_start:line_end]
    print("\nLine 3313 after fix:")
    print("  Hex: %s" % ' '.join('%02X' % b for b in line))
    print("  Text: %s" % repr(line))
