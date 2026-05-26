NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Current line 3313:     "print('='*60)\n"\\r,"
# Should be:             "print('='*60)\n"\\r",
# Fix: Change \\r," to \\r",
# i.e., swap the comma and quote positions

# The bytes at end of line 3313 are: 5C 72 2C 22
# We want: 5C 72 22 2C
search = b'\\r,"'
replace = b'\\r",'

# Find and replace ALL occurrences
count = 0
while True:
    p = raw.find(search)
    if p < 0:
        break
    # Check this is the right one (around the print statement area)
    if 166000 < p < 167000:
        print("Found target at byte %d: %s" % (p, repr(raw[p-30:p+20])))
        raw[p+2], raw[p+3] = raw[p+3], raw[p+2]  # swap
        count += 1
        print("Fixed!")
    else:
        # Replace but don't count as target
        raw[p:p+len(search)] = replace
        print("Replaced non-target at byte %d" % p)

print("Total fixes: %d" % count)

with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
print("Saved.")

# Verify
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    # Show context
    text = raw.decode('utf-8', errors='replace')
    lines = text.split('\n')
    if e.lineno <= len(lines):
        print("Error line: %s" % repr(lines[e.lineno-1]))
