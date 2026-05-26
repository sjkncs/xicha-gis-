NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find exact error
try:
    nb = json.loads(content)
except json.JSONDecodeError as e:
    pos = e.pos
    ln = content[:pos].count('\n') + 1
    col = pos - content.rfind('\n', 0, pos) - 1
    print("Error: %s at char %d, line %d col %d" % (e.msg, pos, ln, col))
    
    # Get the line
    line_start = content.rfind('\n', 0, pos) + 1
    line_end = content.find('\n', pos)
    error_line = content[line_start:line_end]
    
    print("\nLine %d (len %d):" % (ln, len(error_line)))
    print(repr(error_line))
    
    # Show char-by-char from col 40 to col 50
    print("\nChars at col 40-55:")
    for i in range(max(0, col-5), min(len(error_line), col+10)):
        c = error_line[i]
        print("  col %d: %r" % (i, c))

# Now let's also load in binary and check
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("\n\n=== Binary analysis ===")
# Find the error line in binary
# Line 3348 in the text corresponds to what in binary?
lines_text = content.split('\n')
byte_pos = 0
for i in range(ln-1):
    byte_pos = raw.find(b'\n', byte_pos) + 1
    
print("Line %d starts at byte %d" % (ln, byte_pos))

# Show bytes from byte_pos+40 to byte_pos+60
chunk = raw[byte_pos+40:byte_pos+80]
print("\nBytes at byte_pos+%d to %d:" % (40, 40+len(chunk)))
print("  hex:", chunk.hex())
print("  repr:", repr(chunk))
print("  decoded:", chunk.decode('utf-8', errors='replace'))
