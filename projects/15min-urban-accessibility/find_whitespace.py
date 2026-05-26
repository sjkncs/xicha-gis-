NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The issue: after b',\r\n' (closing a string + comma + line ending)
# There's b'    ' (4 spaces) then the next string starts
# This means there's an empty/whitespace-only line between two strings

# Let me find all occurrences of: b',\r\n    \n' (4 spaces followed by LF)
# This would be: comma, CR, LF, 4 spaces, LF

# Actually looking at the hex dump again:
# ...22 2C 0D 0A 20 20 20 20 22...
# = quote, comma, CR, LF, space, space, space, space, quote
# So the pattern is: b',\r\n    "'

# But wait, there's no CR before the 4 spaces, only LF
# Let me search for this pattern

# The 4 spaces after CRLF might indicate a continuation or error
# Pattern: b'\r\n    \n' but we need to see if there's content after

# Let me search for: b',\r\n    ' (comma, CRLF, 4 spaces)
# This represents a whitespace-only line between array elements

search = b',\r\n    '
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1
    if len(positions) > 5:
        break

print("Found %d occurrences of b',\\r\\n    '" % len(positions))
for p in positions:
    print("  byte %d: %s" % (p, repr(raw[p:p+30])))
    print("  After (next 20 bytes): %s" % repr(raw[p:p+50]))

# If I see what comes after the 4 spaces, I can fix properly
# The goal is to see: b',\r\n    "' (whitespace then quote for next string)
# vs b',\r\n    \r\n' (whitespace line then more content)
