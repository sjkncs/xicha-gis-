NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Let me find the exact pattern: we need to find the line that has print('='*60)
# and ends with \\", (backslash-quote-comma, i.e., \r",)
# Actually let me just search for the byte pattern that represents this content

# Search for print('='*60)\n"\\r",
# bytes: 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 22 2C

search_pattern = b"print('='*60)\\n\"\\r\","
print("Searching for: %s" % repr(search_pattern))

positions = []
start = 0
while True:
    p = raw.find(search_pattern, start)
    if p < 0:
        break
    positions.append(p)
    start = p + 1

print("Found %d occurrences" % len(positions))
for p in positions:
    ctx_before = repr(raw[p-30:p])
    ctx_after = repr(raw[p:p+30])
    print("  Pos %d: before=%s after=%s" % (p, ctx_before, ctx_after))

# The correct ending should NOT have a quote before the comma
# print('='*60)\n"\\r",
# bytes: 70 72 69 6E 74 28 27 3D 27 2A 36 30 29 5C 6E 22 5C 72 2C

correct_pattern = b"print('='*60)\\n\"\\r\","
print("\nCorrect pattern: %s" % repr(correct_pattern))
print("Lengths: search=%d correct=%d" % (len(search_pattern), len(correct_pattern)))

# Check if the pattern already exists
if correct_pattern in raw:
    print("CORRECT PATTERN ALREADY EXISTS!")
else:
    print("Correct pattern NOT found - need to fix")

# Check the last occurrence
if positions:
    p = positions[-1]
    print("\nLast occurrence at byte %d:" % p)
    print("  Bytes: %s" % ' '.join('%02X' % b for b in raw[p:p+len(search_pattern)]))
    
    # The string "print('='*60)\n"\\r"," should be "print('='*60)\n"\\r",
    # That is: the quote before the comma should be REMOVED
    # Current: 5C 72 22 2C (\r",)
    # Correct: 5C 72 2C (\r,)
    
    # Position of the quote we need to remove:
    # It's right after \\r and before ,
    quote_pos = p + len(search_pattern) - 2  # Last 2 are 22 2C, remove 22
    print("  Byte at %d: 0x%02X" % (quote_pos, raw[quote_pos]))
    print("  Byte at %d: 0x%02X" % (quote_pos+1, raw[quote_pos+1]))
    
    # Verify it's quote-comma
    if raw[quote_pos] == 0x22 and raw[quote_pos+1] == 0x2C:
        print("\n  CONFIRMED: Extra quote at byte %d" % quote_pos)
        print("  Removing...")
        del raw[quote_pos]
        
        with open(NOTEBOOK_PATH, 'wb') as f:
            f.write(raw)
        print("  Saved.")
        
        try:
            nb = json.loads(raw)
            print("\n  SUCCESS! %d cells" % len(nb['cells']))
        except json.JSONDecodeError as e:
            print("  Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
