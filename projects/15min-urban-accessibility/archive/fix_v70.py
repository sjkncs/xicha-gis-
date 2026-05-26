NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Line 3313 raw bytes: 20 20 20 20 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C 0A
#                      ^spaces ^"  ^p  r  i  n  t  (  '  =  '  *  6  0  )  \  n  "  \  r  "  ,  \n
#
# The problem: bytes 22-24 are: 22 2C (quote, comma)
# Should be: 2C (comma only) at byte 22
#
# In other words: \"\\r"," should be \"\\r",
# Fix: Remove byte 22 (the extra quote)

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

print("Line 3313 bytes (%d-%d): %s" % (line_start, line_end, repr(raw[line_start:line_end+1])))
print("Hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_end+1]))

# Target: byte 22 relative to line start is the extra quote
# Line starts at line_start, byte 22 is line_start + 22
extra_quote_pos = line_start + 22
print("\nByte at %d: 0x%02X = '%s'" % (extra_quote_pos, raw[extra_quote_pos], chr(raw[extra_quote_pos])))
print("Next byte: 0x%02X" % raw[extra_quote_pos + 1])

# Check: byte 22 should be 0x2C (comma), not 0x22 (quote)
# Remove byte 22
print("\nRemoving extra quote at byte %d..." % extra_quote_pos)
del raw[extra_quote_pos]

print("New line 3313: %s" % repr(raw[line_start:line_start+26]))
print("New hex: %s" % ' '.join('%02X' % b for b in raw[line_start:line_start+26]))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("\nSaved.")

try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
