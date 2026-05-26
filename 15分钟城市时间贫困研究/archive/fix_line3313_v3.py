NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The issue: a literal CR (0D) in the JSON string needs to be escaped as \r (5C 72)
# Current: ...\n"0D 0A 20 20 20 5D... = ...\n"<CR><LF>spaces]...
# Should be: ...\n"5C 72 0A 20 20 20 5D... = ...\n"\r<LF>spaces]...

# But wait, looking at the hex:
# ...22 5C 72 22 0A... = quote, backslash, r, quote, LF
# This is actually valid: string ends with \r" followed by LF
# But the \r is INSIDE the string value

# Let me re-examine:
# After the string value ends (with "), we should see either , or ]
# But we see: " \r " LF spaces ]
# The " before \r is the closing quote
# But then there's \r INSIDE the string value

# Actually the issue is:
# The string VALUE contains literal \r
# But in JSON, strings can contain literal \r as long as it's escaped

# Let me check: is the CR escaped?
# Current bytes: 22 5C 72 22 0A
# = quote, backslash, r, quote, LF
# The backslash IS there, so \r IS escaped

# But wait - let me re-check the bytes more carefully
# Find the print('='*60) statement

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
    # Show 50 bytes after
    chunk = raw[p:p+50]
    print("\n%d: byte %d" % (i, p))
    print("  Hex: %s" % ' '.join('%02X' % b for b in chunk))
    print("  Text: %s" % chunk.decode('utf-8', errors='replace'))

# Check the actual bytes
target = positions[-1]

# Look at what comes after the print statement
after = raw[target+17:target+35]  # after print('='*60)
print("\n\nBytes after print('='*60):")
print("  Hex: %s" % ' '.join('%02X' % b for b in after))
print("  Text: %s" % repr(after))

# Check if there's a quote before print
before = raw[target-4:target+1]
print("\nBefore print:")
print("  Hex: %s" % ' '.join('%02X' % b for b in before))
print("  Text: %s" % repr(before))
