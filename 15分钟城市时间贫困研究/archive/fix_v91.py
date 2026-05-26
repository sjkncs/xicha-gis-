NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json, ast
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Try to find the problem by looking at what Python's json module sees
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d, pos %d" % (e.msg, e.lineno, e.colno, e.pos))
    
    # Get the text
    text = raw.decode('utf-8', errors='replace')
    
    # Find what character is at the error position
    if e.pos < len(text):
        print("\nChar at pos %d: 0x%04X = '%s'" % (e.pos, ord(text[e.pos]), repr(text[e.pos])))
        print("Context: %s" % repr(text[max(0,e.pos-50):e.pos+50]))
    
    # Let me manually trace the JSON parsing
    print("\n=== Manual JSON trace ===")
    
    # Try to parse incrementally
    lines = text.split('\n')
    
    # Count LF before error position
    lf_count = text[:e.pos].count('\n')
    print("LF count before error: %d" % lf_count)
    
    # The error is at col 22 of line 3313
    # So in the current file, line 3312 ends at some position
    # Let's find where line 3313 starts
    lf_positions = [i for i, c in enumerate(text) if c == '\n']
    if len(lf_positions) >= 3313:
        line_3313_start = lf_positions[3312] + 1 if len(lf_positions) > 3312 else 0
        line_3313_end = lf_positions[3313] if len(lf_positions) > 3313 else len(text)
        
        line_3313 = text[line_3313_start:line_3313_end]
        print("\nLine 3313 (%d-%d):" % (line_3313_start, line_3313_end))
        print("  %s" % repr(line_3313))
        print("\n  Col 22 (pos %d): 0x%04X = '%s'" % (
            e.colno-1, ord(line_3313[e.colno-1]) if e.colno <= len(line_3313) else 0, 
            line_3313[e.colno-1] if e.colno <= len(line_3313) else '?'))

# Let me try a different approach: fix the file by removing line 3313 and replacing with correct content
print("\n=== Fixing by replacement ===")

# The correct line 3313 content should be:
# "    print('='*60)\\n"\\r",\r\n"
# In Python string: '    "print(\'=\'*60)\\n"\\r",\r\n'
correct_line = '    "print(\'=\'*60)\\n"\\r",\r\n'

print("Correct line: %s" % repr(correct_line))

# Find the line in the text and replace it
lf_positions_text = [i for i, c in enumerate(text) if c == '\n']
line_3313_start = lf_positions_text[3312] + 1 if len(lf_positions_text) > 3312 else 0
line_3313_end = lf_positions_text[3313] if len(lf_positions_text) > 3313 else len(text)

print("Line 3313 currently: %s" % repr(text[line_3313_start:line_3313_end]))
print("Line 3313 length: %d" % (line_3313_end - line_3313_start))

# Check if there's a CR before the LF
if line_3313_end > 0 and text[line_3313_end-1] == '\r':
    print("Line ends with CR")
else:
    print("Line does NOT end with CR")
    # Need to add CR before the LF
    print("Inserting CR...")
    correct_line_with_cr = '    "print(\'=\'*60)\\n"\\r",\r\n'
    # Actually, let me just fix by replacing
