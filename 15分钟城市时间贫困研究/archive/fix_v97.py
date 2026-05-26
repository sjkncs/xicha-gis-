NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check bytes 149460-149480
print("Bytes 149460-149480:")
for i in range(149460, min(149480, len(raw))):
    c = chr(raw[i]) if 32 <= raw[i] < 127 else '?'
    print("  Byte %d: 0x%02X = '%s'" % (i, raw[i], c))

# Check text positions 149460-149480
print("\nText positions 149460-149480:")
for i in range(149460, min(149480, len(text))):
    c = text[i]
    print("  Pos %d: 0x%04X = '%s'" % (i, ord(c), repr(c)))

# Check line numbers
print("\n=== Line number mapping ===")
lf_positions = [i for i, c in enumerate(text) if c == '\n']
print("Total LF: %d" % len(lf_positions))
if len(lf_positions) > 3312:
    print("LF[3312] (start of line 3313): %d" % lf_positions[3312])
if len(lf_positions) > 3311:
    print("LF[3311] (end of line 3312): %d" % lf_positions[3311])
print("\nLine 3312: bytes %d to %d" % (lf_positions[3311]+1, lf_positions[3312]))
print("Line 3313: bytes %d to %s" % (lf_positions[3312]+1, lf_positions[3313] if len(lf_positions) > 3313 else 'end'))

# Show lines 3312 and 3313
lines = text.split('\n')
print("\nLine 3312: %s" % repr(lines[3311]))
print("Line 3313: %s" % repr(lines[3312]))

# Show raw bytes of line 3312
lf_pos = lf_positions[3311]
line_end = lf_positions[3312]
print("\nLine 3312 raw bytes (%d-%d):" % (lf_pos+1, line_end))
line_bytes = raw[lf_pos+1:line_end+1]
print("  Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
print("  Text: %s" % repr(line_bytes))

# The issue is at position 149465 in TEXT
# But byte 149465 in RAW might be different
print("\nRaw byte at text pos 149465: 0x%02X" % raw[149465])
print("Text char at pos 149465: 0x%04X = '%s'" % (ord(text[149465]), repr(text[149465])))
