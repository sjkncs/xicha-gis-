NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The problem line is:     "print('='*60)\n\r"",
# We want:               "print('='*60)\n\r",
# 
# In raw bytes, the last part should be:
# 5C 6E 72 22 2C (meaning \n r " ,)
# But we have:
# 5C 6E 72 22 22 2C (meaning \n r " " ,)

# Search for the print('='*60) statement
search = b"print('='*60)"
positions = []
start = 0
while True:
    p = raw.find(search, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences of print('='*60)" % len(positions))
for p in positions:
    # Show context
    ctx = raw[p:p+50]
    print("\nByte %d:" % p)
    print("  Hex: %s" % ' '.join('%02X' % b for b in ctx))
    print("  Text: %s" % repr(ctx))
    
    # Check for double-quote pattern
    for i, b in enumerate(ctx):
        if b == 0x22:  # Quote
            print("  Quote at offset %d" % i)

print("\n=== Looking for double-quote pattern ===")
# Search for ",", (quote, comma) pattern
for i in range(len(raw)-2):
    if raw[i] == 0x22 and raw[i+1] == 0x22 and raw[i+2] == 0x2C:
        print("Double-quote-comma at byte %d: %s" % (i, repr(raw[i-30:i+30])))
