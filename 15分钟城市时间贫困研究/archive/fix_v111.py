NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The problem: line 3313 ends with \n"\\r", where \\r should be \r
# We need to find 5C 5C 72 in the line and replace with 5C 72

text = raw.decode('utf-8', errors='replace')
lf_positions = [i for i, c in enumerate(text) if c == '\n']

# Line 3313 starts after LF[3311], ends at LF[3312]
l3313_start = lf_positions[3311] + 1
l3313_end = lf_positions[3312]
line_bytes = bytearray(raw[l3313_start:l3313_end])

print("Line 3313 hex:")
print(' '.join('%02X' % b for b in line_bytes))

# Find the double backslash before 'r' - looking for pattern: 5C 5C 72 22 2C
# That is: \\r",
for i in range(len(line_bytes) - 5):
    if (line_bytes[i] == 0x5C and line_bytes[i+1] == 0x5C and 
        line_bytes[i+2] == 0x72 and line_bytes[i+3] == 0x22 and 
        line_bytes[i+4] == 0x2C):
        print("\nFound double backslash at position %d" % i)
        print("Before: %s" % ' '.join('%02X' % line_bytes[i+j] for j in range(-3, 7)))
        
        # Fix: remove one backslash (replace 5C 5C 72 with 5C 72)
        del line_bytes[i+1]  # Remove the second 5C
        
        print("After:  %s" % ' '.join('%02X' % line_bytes[i+j] for j in range(-3, 7)))
        
        # Update the raw bytes
        new_line_bytes = bytes(line_bytes)
        raw = raw[:l3313_start] + new_line_bytes + raw[l3313_end:]
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
