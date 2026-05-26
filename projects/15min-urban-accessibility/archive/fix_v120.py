NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check line 3313
lines = text.split('\n')
print("Total lines: %d" % len(lines))

if len(lines) >= 3313:
    line_3313 = lines[3312]
    print("\nLine 3313 (%d chars):" % len(line_3313))
    print("  %s" % repr(line_3313))
    
    # Show character by character
    print("\nChar by char (col: char):")
    for i, c in enumerate(line_3313):
        print("  col %d: %s (0x%02X)" % (i+1, repr(c), ord(c)))

# The print('='*60) is around text position 149449
# Let me find what line that's on
print("\n=== Finding print statement ===")
search = "print('='*60)"
pos = text.find(search)
print("Found at text position %d" % pos)

# Count lines before this position
lines_before = text[:pos].count('\n')
print("Line number: %d" % (lines_before + 1))

# Show context
print("Context: %s" % repr(text[pos-50:pos+60]))
