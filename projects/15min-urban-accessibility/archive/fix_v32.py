NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read raw bytes
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find the area around 'cells": [' close
# Looking for: '   ],\r\n   }\r\n ]\r\n "metadata"'
# In hex: 20 20 20 5D 2C 0D 0A 20 20 20 7D 0D 0A 20 5D 0D 0A 20 22 6D

# Search for the pattern
pattern = b'   ],\r\n   }\r\n ]'
pos = raw.find(pattern)
print("Pattern '   ],\\r\\n   }\\r\\n ]' at byte: %d" % pos)

if pos >= 0:
    print("\nContext around pattern:")
    ctx = raw[pos-50:pos+100]
    print(repr(ctx.decode('utf-8', errors='replace')))
    
    # Fix: Replace '   },\r\n ]' with '   },\r\n],'
    # OR: Replace '   }\r\n' with '   },\r\n'
    # AND: Replace ' ]\r\n' with '],\r\n'
    
    # But wait - is this the LAST cell? If yes, no comma on cell close
    # If there are more cells, comma needed
    
    # Let's check - is there any Section 13 cell after this?
    if b'id=' + b"'13'" in raw[pos:]:
        print("\nThere's more content after - this is NOT the last cell")
    else:
        print("\nThis appears to be the last cell - no comma needed on cell close")
    
    # Actually looking at the error: "Illegal trailing comma before end of array"
    # This means the parser sees something like: [item1, item2,] <- trailing comma
    
    # Let me check: is line 3313 actually TWO lines?
    # Line 3313: '    "print(\'=\'*60)\\n",\n'
    # Line 3314: '    "print(\'=\'*60)\\n",\n'  <- DUPLICATE!
    
    # Let me count lines more carefully
    print("\n\nCounting lines in file...")
    line_breaks = raw.count(b'\n')
    print("Total newlines: %d" % line_breaks)
    
    # The last source line should be the LAST string in the array
    # If there's a duplicate line 3313, that's the problem
    
    # Let's find all occurrences of "print(\'=\'*60)" 
    search = b"print(\\'=\\'*60)"
    positions = []
    start = 0
    while True:
        p = raw.find(search, start)
        if p < 0:
            break
        positions.append(p)
        start = p + 1
    
    print("\nFound %d occurrences of print('='*60)" % len(positions))
    for i, p in enumerate(positions):
        print("  %d at byte %d: %s" % (i+1, p, repr(raw[p:p+30])))
