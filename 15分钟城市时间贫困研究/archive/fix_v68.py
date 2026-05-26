NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("=== Lines 3310-3320 ===")
for i in range(3309, min(3320, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

print("\n=== Checking for bare CR (0x0D) ===")
bare_cr_count = 0
for i, b in enumerate(raw):
    if b == 0x0D and (i == 0 or raw[i-1] != 0x0A):
        if i+1 < len(raw) and raw[i+1] != 0x0A:
            bare_cr_count += 1
            if bare_cr_count <= 5:
                ctx = raw[max(0,i-20):i+20]
                print("Bare CR at byte %d: %s" % (i, repr(ctx)))
print("Total bare CR: %d" % bare_cr_count)

print("\n=== JSON parse attempt ===")
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d, pos %d" % (e.msg, e.lineno, e.colno, e.pos))
    
    # Find the actual byte position
    json_text = raw.decode('utf-8', errors='replace')
    
    # Count lines up to error line
    line_count = 0
    char_count = 0
    byte_pos = 0
    for i, c in enumerate(json_text):
        if c == '\n':
            line_count += 1
            if line_count == e.lineno:
                byte_pos = i
                break
        char_count += 1
        if line_count == e.lineno - 1:
            byte_pos = i
    
    print("Byte range for error line: ~%d to ~%d" % (byte_pos, byte_pos+200))
    print("Content: %s" % repr(raw[byte_pos:byte_pos+200]))
    
    # Also check line before
    prev_newline = raw.rfind(b'\n', 0, byte_pos)
    prev2_newline = raw.rfind(b'\n', 0, prev_newline)
    print("\nPrevious line content:")
    print(repr(raw[prev2_newline+1:prev_newline+1]))
