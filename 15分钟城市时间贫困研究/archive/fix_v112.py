NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Check raw bytes around position 149400-149500
print("=== Raw bytes 149400-149500 ===")
for i in range(149400, 149500, 20):
    chunk = raw[i:i+20]
    # Find LF in chunk
    for j, b in enumerate(chunk):
        if b == 0x0A:  # LF
            print("LF at raw byte %d" % (i+j))
    hex_str = ' '.join('%02X' % b for b in chunk)
    print("%d: %s" % (i, hex_str))

# Look for the full print('='*60) statement in raw bytes
# Search for the pattern: print('='*60
search = b"print('='*60"
pos = raw.find(search)
if pos >= 0:
    print("\n=== Found print('='*60) at raw byte %d ===" % pos)
    print("Context (100 bytes): %s" % ' '.join('%02X' % b for b in raw[pos:pos+100]))
    
# Also search for \\r",
search2 = b'\\r",'
pos2 = raw.find(search2)
if pos2 >= 0:
    print("\n=== Found \\r\", at raw byte %d ===" % pos2)
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2-30:pos2+50]))

# Search for ')",' which should be after the print statement
search3 = b"')'"
pos3 = raw.find(search3)
if pos3 >= 0:
    print("\n=== Found ')'\" at raw byte %d ===" % pos3)
    print("Context: %s" % ' '.join('%02X' % b for b in raw[pos3-20:pos3+30]))
