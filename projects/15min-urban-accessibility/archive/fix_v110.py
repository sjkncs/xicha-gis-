NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find "01_nanshan_road_network" in the text
search = "01_nanshan_road_network"
pos = text.find(search)
if pos >= 0:
    print("Found '01_nanshan_road_network' at text position %d" % pos)
    print("Context (200 chars): %s" % repr(text[pos-30:pos+200]))
    
    # Check what comes after
    after = text[pos+100:pos+200]
    print("\nAfter +100 chars: %s" % repr(after))

# Find the end of this print statement
# Look for "print('='*60" in the text
search2 = "print('='*60"
pos2 = text.find(search2)
if pos2 >= 0:
    print("\nFound 'print(\"=\"*60' at text position %d" % pos2)
    print("Context: %s" % repr(text[pos2:pos2+80]))

# Let me check the line structure around line 3313
lines = text.split('\n')
print("\n=== Lines 3300-3340 ===")
for i in range(3299, 3340):
    if i < len(lines):
        line = lines[i]
        if 'road_network' in line or 'print(' in line or 'Fig' in line:
            print("Line %d: %s" % (i+1, repr(line[:150])))
