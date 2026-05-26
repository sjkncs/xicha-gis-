NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find line 3313 start and end positions
text = raw.decode('utf-8', errors='replace')
lf_positions = [i for i, c in enumerate(text) if c == '\n']

# Line 3313: starts after lf_positions[3311], ends at lf_positions[3312]
l3313_start = lf_positions[3311] + 1
l3313_end = lf_positions[3312]

print("Line 3313 bytes (%d-%d):" % (l3313_start, l3313_end))
line_bytes = raw[l3313_start:l3313_end]
print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
print("Chars: %s" % ''.join(chr(b) if 32 <= b < 127 else '.' for b in line_bytes))

# The problem: 5C 5C 72 = \\r (escaped backslash + r literal)
# Should be: 5C 72 = \r (carriage return escape)
# Find 5C 5C 72 in the line
for i, b in enumerate(line_bytes):
    if i+2 < len(line_bytes) and b == 0x5C and line_bytes[i+1] == 0x5C and line_bytes[i+2] == 0x72:
        pos = l3313_start + i
        print("\nFound 5C 5C 72 (escaped backslash+r) at byte %d" % pos)
        print("Context: %s" % ' '.join('%02X' % raw[pos+j] for j in range(-5, 8)))
        
        # Fix: replace 5C 5C 72 with 5C 72
        # But we need to be careful - there might be more \\r sequences
        
# Also check: is the \n escape correct?
# In JSON, \n is 5C 6E
# If we have 5C 6E in line 3313, that's correct
# If we have something else, that's wrong

# Let me look at the full line more carefully
print("\n=== Full line 3313 analysis ===")
i = 0
while i < len(line_bytes):
    b = line_bytes[i]
    if b == 0x5C and i+1 < len(line_bytes):  # Backslash escape
        next_b = line_bytes[i+1]
        if next_b == 0x6E:
            print("  pos %d: \\n (newline)" % i)
            i += 2
        elif next_b == 0x72:
            print("  pos %d: \\r (CR)" % i)
            i += 2
        elif next_b == 0x5C:
            print("  pos %d: \\\\ (backslash literal)" % i)
            i += 2
        elif next_b == 0x22:
            print("  pos %d: \\\" (quote)" % i)
            i += 2
        else:
            print("  pos %d: \\%s (0x%02X)" % (i, chr(next_b), next_b))
            i += 2
    else:
        c = chr(b) if 32 <= b < 127 else '.'
        print("  pos %d: '%s' (0x%02X)" % (i, c, b))
        i += 1

# Now fix the \\r issue
# In line 3313, the second \r (after the comma) should be a proper escape
# Current: ,\\r",
# Should be: ,\r",

print("\n=== Fixing \\r escape ===")
# The first \r in line 3313 should be correct (at pos ~20)
# The second \r (after the comma) at position ~23 is wrong

# Find ",5C 5C 72," pattern in line 3313
# That is: 22 2C 5C 5C 72 22 2C
for i in range(len(line_bytes) - 6):
    if (line_bytes[i] == 0x22 and line_bytes[i+1] == 0x2C and 
        line_bytes[i+2] == 0x5C and line_bytes[i+3] == 0x5C and 
        line_bytes[i+4] == 0x72 and line_bytes[i+5] == 0x22 and 
        line_bytes[i+6] == 0x2C):
        pos = l3313_start + i
        print("Found bad \\r at byte position %d" % pos)
        print("Before: %s" % ' '.join('%02X' % raw[pos+j] for j in range(-3, 8)))
        
        # Fix: replace 5C 5C 72 with 5C 72
        raw[pos+2] = 0x72  # Change second 5C to 72
        raw[pos+3:pos+4] = b''  # Remove the extra 5C
        
        print("After fix: %s" % ' '.join('%02X' % raw[pos+j] for j in range(-3, 8)))
        break

# Save
with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

# Test
try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
