NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check current JSON lines
lines = text.split('\n')
print("Total lines: %d" % len(lines))

# Line 3313 (1-indexed)
if len(lines) >= 3313:
    line_3313 = lines[3312]
    print("\nLine 3313 (%d chars):" % len(line_3313))
    print("  %s" % repr(line_3313))
    
    # Check character at col 22 (1-indexed)
    if len(line_3313) >= 22:
        print("\nChar at col 22: %s (0x%02X)" % (repr(line_3313[21]), ord(line_3313[21])))

# Let me find the print('='*60) statement and check its context
search = "print('='*60)"
pos = text.find(search)
if pos >= 0:
    print("\nFound print('='*60) at text position %d" % pos)
    print("Context: %s" % repr(text[pos-20:pos+50]))

# Check if the \r is now correct
search2 = "建筑AOI分析完成"
pos2 = text.find(search2)
if pos2 >= 0:
    print("\nFound '建筑AOI分析完成' at text position %d" % pos2)
    # Check what follows
    after = text[pos2+20:pos2+60]
    print("After +20: %s" % repr(after))
