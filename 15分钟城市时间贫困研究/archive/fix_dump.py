NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Show hex dump of last 300 bytes
print("=== Last 300 bytes (hex + ASCII) ===")
end = raw[-300:]
for i in range(0, len(end), 16):
    chunk = end[i:i+16]
    hex_part = ' '.join('%02X' % b for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print('%04X: %-48s | %s' % (len(raw)-300+i, hex_part, ascii_part))

print("\n=== Decoded last 300 bytes ===")
print(repr(end.decode('utf-8', errors='replace')))

# Now let's find what's between the Section 13 content and metadata
id13_idx = raw.find(b"id='13'")
meta_idx = raw.find(b'"metadata":')

print("\n\n=== Section 13 header cell area ===")
print("id='13' at: %d" % id13_idx)
print("'metadata' at: %d" % meta_idx)
print("Gap: %d bytes" % (meta_idx - id13_idx))

# Show raw bytes from id='13' to metadata
area = raw[id13_idx:meta_idx+20]
print("\nRaw bytes (%d bytes):" % len(area))
for i in range(0, len(area), 16):
    chunk = area[i:i+16]
    hex_part = ' '.join('%02X' % b for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print('%04X: %-48s | %s' % (id13_idx+i, hex_part, ascii_part))
