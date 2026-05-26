NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Check JSON at specific positions
print("=== Checking JSON structure at key lines ===")
print("Line 1 (should be {{): %s" % repr(lines[0]))
print("Line 2 (should be 'cells': [): %s" % repr(lines[1]))
print("Line 3 (should be first cell): %s" % repr(lines[2].strip()))

# Count brackets to find where the cells array really closes
print("\n=== Bracket counting from end ===")
depth = 0
cells_array_closed = False
for i in range(len(lines)-1, -1, -1):
    line = lines[i].strip()
    for ch in line:
        if ch == '{' or ch == '[':
            depth += 1
        elif ch == '}' or ch == ']':
            depth -= 1
    
    if depth == 1 and '],' in line and not cells_array_closed:
        print("Cells array CLOSES at line %d: %s" % (i+1, repr(line)))
        cells_array_closed = True
        break

print("\n=== Last 20 lines ===")
for i in range(max(0, len(lines)-20), len(lines)):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# The error is at line 3313, col 23
# Let me look at what the parser sees BEFORE line 3313
print("\n=== Lines 3305-3315 ===")
for i in range(3304, min(3315, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# Check: is line 3313 supposed to be inside the source array?
# Find the last "source": [ before line 3313
print("\n=== Finding source array containing line 3313 ===")
source_depth = 0
in_source = False
source_start = None
for i in range(len(lines)):
    stripped = lines[i].strip()
    if '"source": [' in stripped:
        source_start = i + 1
        in_source = True
        source_depth = 1
    elif in_source:
        # Track nested brackets
        for ch in stripped:
            if ch == '[':
                source_depth += 1
            elif ch == ']':
                source_depth -= 1
        if source_depth == 0:
            print("Source array %d to %d" % (source_start, i+1))
            if i+1 >= 3313:
                print("  -> Line 3313 is INSIDE this source array")
                # Show content
                for j in range(source_start-1, i+2):
                    if j+1 >= 3310:
                        print("  Line %d: %s" % (j+1, repr(lines[j][:80])))
                break
            in_source = False
