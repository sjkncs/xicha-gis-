NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Line 3313 should be: '    "print(\'=\'*60)\\n",'
# But it might be missing the comma

# Find the last print('='*60) in the file
search = b"print('='*60)"
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences" % len(positions))

for i, p in enumerate(positions):
    # Show context
    chunk = raw[p-10:p+40]
    print("  %d: byte %d: %s" % (i, p, repr(chunk)))

# The last one is the problematic one
target = positions[-1]
print("\nTarget at byte: %d" % target)
print("Context: %s" % repr(raw[target-20:target+50]))

# Check what's before 'print' - should be a quote
if target > 5:
    before = raw[target-5:target]
    print("Before: %s" % repr(before))
    
    # Check what's after - should be comma then newline
    after = raw[target+17:target+25]  # after print('='*60)
    print("After (17-25): %s" % repr(after))
