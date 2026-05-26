NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The error is at line 3313, col 22
# Let me trace through what JSON parser sees

# JSON uses \n (LF) as line separator
# \r (CR) inside strings should be \r (escaped) not literal CR

# Let me check if there are literal CR bytes in the problematic area
# Search for CR (0D) that might be causing issues

# Find the print statement area
search = b"print('='*60)"
pos = raw.find(search)
if pos >= 0:
    print("Found print at byte: %d" % pos)
    
    # Show full context
    chunk = raw[pos-50:pos+100]
    print("\nContext (%d bytes):" % len(chunk))
    print("Hex: %s" % ' '.join('%02X' % b for b in chunk))
    
    # Show as text
    print("\nAs text: %s" % chunk.decode('utf-8', errors='replace'))
    
    # Check each byte
    print("\nByte-by-byte analysis:")
    for i, b in enumerate(chunk[:30]):
        if 32 <= b < 127:
            char = chr(b)
        elif b == 0x0D:
            char = '<CR>'
        elif b == 0x0A:
            char = '<LF>'
        else:
            char = '?'
        print("  [%3d] 0x%02X = %s" % (i, b, char))
