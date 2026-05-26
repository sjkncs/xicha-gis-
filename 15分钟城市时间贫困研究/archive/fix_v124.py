NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The error at line 3313 col 22 in json.loads
# json.loads uses the text content (LF-split lines)
# Line 3313 is after 3312 LFs

# Find LF positions
text = raw.decode('utf-8', errors='replace')
lf_positions = [i for i, c in enumerate(text) if c == '\n']

# Line 3313 starts after lf_positions[3311] and ends at lf_positions[3312]
l3313_start = lf_positions[3311] + 1
l3313_end = lf_positions[3312]

print("Line 3313 bytes (%d-%d):" % (l3313_start, l3313_end))
line_bytes = raw[l3313_start:l3313_end]
print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
print("Chars: %s" % ''.join(chr(b) if 32 <= b < 127 else '.' for b in line_bytes))

# Now let's trace through what JSON sees at col 22
print("\n=== Byte-by-byte analysis ===")
i = 0
col = 1
while i < len(line_bytes):
    b = line_bytes[i]
    char = chr(b) if 32 <= b < 127 else '.'
    print("col %d (byte %d): 0x%02X = '%s'" % (col, l3313_start + i, b, char))
    
    # Track position
    if col == 22:
        print("  <-- ERROR POSITION")
        print("  At col 22, JSON finds 0x%02X" % b)
        if b == 0x5C:
            print("  This is a backslash!")
            print("  Next byte: 0x%02X" % (line_bytes[i+1] if i+1 < len(line_bytes) else 0))
    
    i += 1
    col += 1

# Also check: the \\n in the string should be bytes 5C 6E
# Let's verify this
print("\n=== Looking for \\n pattern ===")
for i in range(len(line_bytes) - 1):
    if line_bytes[i] == 0x5C and line_bytes[i+1] == 0x6E:
        print("Found \\n at byte offset %d (col %d)" % (i, i+1))
        print("Context: %s" % ' '.join('%02X' % b for b in line_bytes[max(0,i-3):i+8]))
