NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))
print("CRLF count: %d" % raw.count(b'\r\n'))
print("LF-only count: %d" % raw.count(b'\n') - raw.count(b'\r\n'))

# Show last 100 bytes as hex
print("\nLast 100 bytes:")
print(' '.join('%02X' % b for b in raw[-100:]))

# Find the Section 13 area
idx = raw.find(b"id='13'")
if idx >= 0:
    print("\nSection 13 area (%d bytes):" % (idx+400-idx))
    area = raw[idx:idx+400]
    for i in range(0, len(area), 32):
        chunk = area[i:i+32]
        hex_part = ' '.join('%02X' % b for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print('%04X: %-96s | %s' % (idx+i, hex_part, ascii_part))
