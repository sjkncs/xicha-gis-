NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Find the Fig11 cell start
for i, line in enumerate(lines):
    if 'Fig11' in line and 'print' in line:
        print("Line %d: %s" % (i+1, repr(line[:80])))
        if i > 3300:
            break

print("\n\nContext around the Fig11 cell close:")
for i in range(3308, 3320):
    print("%d: %s" % (i+1, repr(lines[i])))

# Let me also check what the correct Fig11 cell structure should be
# by looking at a similar cell earlier in the file
print("\n\nLooking for cell closings earlier in file...")
for i in range(len(lines)):
    if lines[i].strip() == '},':
        # Check context
        prev = lines[i-1] if i > 0 else ''
        next_line = lines[i+1] if i+1 < len(lines) else ''
        if 'source' not in prev and '],' in next_line:
            print("Line %d: '%s'" % (i+1, lines[i].strip()))
            print("Line %d: '%s'" % (i+2, lines[i+1].strip()))
            print("Line %d: '%s'" % (i+3, lines[i+2].strip()))
            print()
            if i > 3000:
                break
