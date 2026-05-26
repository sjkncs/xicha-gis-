NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Show 60 bytes around byte 166660
print("=== 60 bytes around 166660 ===")
area = raw[166630:166720]
for i in range(0, len(area), 20):
    chunk = area[i:i+20]
    hex_part = ' '.join('%02X' % b for b in chunk)
    ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print('%04X: %-60s | %s' % (166630+i, hex_part, ascii_part))

print("\n\n=== Decoded ===")
print(repr(raw[166630:166720].decode('utf-8', errors='replace')))

# Now search for the actual pattern byte by byte
# Looking for: 20 20 20 20 22 20 7D 2C (4-space " 2-space },)
print("\n\n=== Searching for 4-space quote pattern ===")
search = b'    " }'
count = raw.count(search)
print("'    \" }' found %d times" % count)
pos = raw.find(search)
if pos >= 0:
    print("First at %d: %s" % (pos, repr(raw[pos:pos+20])))
    
    # Now check what comes after
    after = raw[pos:pos+50]
    print("\nAfter '    \" }':")
    print(' '.join('%02X' % b for b in after[len(search):]))
