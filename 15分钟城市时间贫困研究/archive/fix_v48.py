NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# From earlier analysis:
# Line 3313 ends with: quote \n " \r LF spaces ] ,
# Let me find the exact position

# Search for: print('='*60)\n"\r\n   ],
# In bytes:
# 22 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 0A 20 20 20 5D 2C

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
for p in positions:
    # Show bytes around this position
    chunk = raw[p:p+80]
    print("\nAt byte %d:" % p)
    print("  Hex: %s" % ' '.join('%02X' % b for b in chunk[:40]))
    
    # Find the end of this string (look for quote followed by \r or end)
    for i, b in enumerate(chunk):
        if b == 0x22 and i > 5:  # quote after start
            print("  Quote at offset %d" % i)
            # Check what follows the quote
            if i + 1 < len(chunk):
                print("  After quote: %02X %02X %02X" % (chunk[i+1], chunk[i+2], chunk[i+3]))
            break
    
    # Also check if there's a comma after the ]
    bracket_pos = chunk.find(bytes([0x5D]))
    if bracket_pos >= 0:
        print("  ] at offset %d" % bracket_pos)
        if bracket_pos + 1 < len(chunk):
            print("  After ]: %02X" % chunk[bracket_pos+1])
