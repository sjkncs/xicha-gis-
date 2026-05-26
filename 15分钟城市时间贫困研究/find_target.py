NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# I made a mistake - need to restore
# Let me reload and find the RIGHT position

# The problematic print statement is on line 3313
# Let me find it more precisely

# Find the print('='*60) that's missing the quote
# It's the one followed by \r"LF

search = b"print('='*60)\\n"
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences of print('='*60)\\n" % len(positions))
for i, p in enumerate(positions):
    # Check what comes after
    chunk = raw[p:p+30]
    print("  %d: byte %d: %s" % (i, p, repr(chunk)))

# The last one (in the problematic cell) should be missing a quote
# Current: '    print('='*60)\\n'
# Should be: '    "print('='*60)\\n",'

# The last occurrence is likely the one we need
target = positions[-1]
print("\nLast occurrence at byte: %d" % target)
print("Context: %s" % repr(raw[target-10:target+40]))

# Check if there's a quote before 'print'
if target > 5:
    before = raw[target-5:target]
    print("Bytes before: %s" % repr(before))
    if before[4] == 0x22:  # quote
        print("Quote exists - this one is OK")
    else:
        print("Missing quote - need to insert at position %d" % (target-5))
