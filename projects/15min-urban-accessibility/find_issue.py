NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Convert to text to find line 2963
text = raw[:146153].decode('utf-8', errors='replace')  # up to error pos
lines = text.split('\n')

# Find the whitespace-only line
for i in range(2900, 3000):
    if i < len(lines):
        line = lines[i]
        if line.strip() == '':
            print("Empty/whitespace line at text line %d: %s" % (i+1, repr(line)))
            
# Now let's look at the raw bytes around the error position
print("\n\nRaw bytes around pos 146153:")
for offset in range(-30, 30):
    pos = 146153 + offset
    if 0 <= pos < len(raw):
        print("  offset %+d (pos %d): 0x%02X (%c)" % (offset, pos, raw[pos], chr(raw[pos]) if 32 <= raw[pos] < 127 else '?'))

# Also check the hex dump of nearby bytes
print("\nHex dump around pos 146153:")
start = max(0, 146153 - 50)
end = min(len(raw), 146153 + 50)
hex_str = ' '.join('%02X' % b for b in raw[start:end])
print(hex_str)
