NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Line 3313 ends with: b'"print(\'=\'*60)\\n"\\r'
# This should be: b'"print(\'=\'*60)\\n"\\r' (escaped \r)
# The current: b'"print(\'=\'*60)\\n"\\r' - backslash is literal, not escape

# In bytes:
# Current: 5C 6E 22 5C 72 = \n " \r  (literal backslash before r)
# Should be: 5C 6E 22 5C 72 = \n " \r (same, but this IS valid JSON escape)
# Wait, \\r in JSON IS a valid escape sequence for carriage return

# But the JSON parser says "Expecting ',' delimiter" at col 22
# Let me look at what's actually at the end of line 3313

# From the output:
# Line 3313: '    "print(\'=\'*60)\\n"\\r'
# = spaces + quote + print('='*60) + \\n + " + \\r
# In bytes this is: quote, backslash, n, quote, backslash, r

# The issue: after the first \\n" there's literally \\r
# which would be: \n (newline escape) + " (quote) + \\ (backslash) + r
# But \\r is not a valid JSON escape! Only \r is.

# Fix: Change \\r to \r (one backslash)
old = b'"print(\\\'=\\\'*60)\\\\n"\\\\r'
new = b'"print(\\\'=\\\'*60)\\\\n"\\r'
pos = raw.find(old)
print("Looking for: %s" % repr(old))

if pos >= 0:
    print("Found at byte: %d" % pos)
else:
    # Try variations
    print("Not found directly. Searching for parts...")
    
    # Search for the pattern in the file
    search = b"print('='*60)"
    positions = []
    start = 0
    while True:
        p = raw.find(search, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
    
    print("Found %d occurrences of print('='*60)" % len(positions))
    for p in positions:
        print("  byte %d: %s" % (p, repr(raw[p-5:p+30])))
