NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find line 3313 by counting LF
line_num = 0
pos = 0
for i, byte in enumerate(raw):
    if byte == 0x0A:
        line_num += 1
        if line_num == 3313:
            pos = i + 1
            break

# Read the line
end = raw.find(b'\x0A', pos)
line = raw[pos:end]
print("Line 3313 raw bytes (%d bytes):" % len(line))
print(' '.join('%02X' % b for b in line))
print()
print("Decoded: %s" % repr(line.decode('utf-8', errors='replace')))

# Count quotes in the line
quote_count = line.count(b'"')
print("\nQuote count: %d" % quote_count)

# If the line is a JSON string, it should have 2 quotes minimum (open and close)
# If there's only 1 quote, the string isn't properly closed
if quote_count == 1:
    print("\nPROBLEM: Line has only 1 quote - string not properly closed!")
    print("Expected: quote at start and quote before comma")
    print("Actual: only one quote")

# Let me also check what comes before and after
print("\n\nContext:")
print("Before line 3313 (last 50 bytes):")
pre = raw[pos-50:pos]
print(' '.join('%02X' % b for b in pre))
print(repr(pre.decode('utf-8', errors='replace')))

print("\nAfter line 3313 (next 50 bytes):")
post = raw[end:end+50]
print(' '.join('%02X' % b for b in post))
print(repr(post.decode('utf-8', errors='replace')))
