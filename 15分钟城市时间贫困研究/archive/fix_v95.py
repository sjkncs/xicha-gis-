NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
line_start = lf_positions[3311] + 1
line_end = lf_positions[3312]

current = raw[line_start:line_end]
print("Current line 3313 (%d bytes):" % len(current))
print("Hex: %s" % ' '.join('%02X' % b for b in current))

# The current line is the Python repr string: "    \"print('='*60)\\n\"\\\\r\",\r\n"
# Which represents the JSON string: 4 spaces + " + print('='*60) + \n + " + \r + " + , + CR + LF

# Let me decode it properly
text = raw[line_start:line_end].decode('utf-8', errors='replace')
print("\nAs text: %s" % repr(text))

# The JSON string VALUE is the content without the surrounding quotes
# In JSON: "    \"print('='*60)\\n\"\\\\r\",\r\n"
# The VALUE is: 4 spaces + " + print('='*60) + \\n + " + \\r + " + , + CR + LF
# In the file, this is represented as bytes

# Let me manually build the correct bytes
# In JSON, \\n is 0x5C 0x6E, \" is 0x22, \\r is 0x5C 0x72
# CR is 0x0D, LF is 0x0A

correct = bytearray()
correct.extend(b'    ')          # 4 spaces
correct.append(0x22)            # "
correct.extend(b"print('='*60)")  # 12 chars
correct.append(0x5C)            # \
correct.append(0x6E)            # n
correct.append(0x22)            # "
correct.append(0x5C)            # \
correct.append(0x72)            # r
correct.append(0x22)            # "
correct.append(0x2C)            # ,
correct.append(0x0D)            # CR
correct.append(0x0A)           # LF

print("\nCorrect line (%d bytes):" % len(correct))
print("Hex: %s" % ' '.join('%02X' % b for b in correct))
print("Text: %s" % repr(correct))

print("\nDifferences:")
for i in range(max(len(current), len(correct))):
    have = current[i] if i < len(current) else None
    want = correct[i] if i < len(correct) else None
    if have != want:
        print("  Byte %d: have 0x%02X, want 0x%02X" % (i, have if have else 0, want if want else 0))

# Overwrite the line
print("\nOverwriting line...")
raw[line_start:line_end] = correct

# Verify
new = raw[line_start:line_start+len(correct)]
if new == correct:
    print("Line now matches correct!")
else:
    print("Still doesn't match")
    print("New: %s" % ' '.join('%02X' % b for b in new))

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
