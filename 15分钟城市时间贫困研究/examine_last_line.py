NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# From the search, we found the context at byte 166417:
# bytearray(b'    "print(\'=\'*60)\\n"\\r\n   ],\r\n   }')

# This means the actual bytes are:
# b'    "print(\'=\'*60)\\n"\\r\n   ],'

# Let's decode what this actually is:
# In Python string representation:
# '    "print(\'=\'*60)\\n"\\r\n   ],'
# = 4 spaces, quote, print('='*60), backslash-n, quote, backslash-r, CR-LF, 3 spaces, ], CR-LF

# In JSON, the string value would be:
# "print('='*60)\n"\r
# Which is: print('='*60) + newline + " + carriage-return

# But in the raw file, what are the actual bytes?
# Let me extract the exact bytes at that position

pos = 166417 - 5  # Go back a bit
end = pos + 60

print("Raw bytes from byte %d to %d:" % (pos, end))
chunk = raw[pos:end]
print("Hex:", ' '.join('%02X' % b for b in chunk))
print("Decoded:", chunk.decode('utf-8', errors='replace'))
print("Repr:", repr(chunk))

# The key question: is the string properly closed with a quote before \r ?
# If the string is: "print('='*60)\n"\r
# Then bytes would be: quote, p, r, i, n, t, (, ', =, *, 6, 0, ), ), backslash, n, quote, backslash, r
# = 22, 70, 72, 69, 6E, 74, 28, 27, 3D, 2A, 36, 30, 29, 29, 5C, 6E, 22, 5C, 72

# Let's check
print("\n\nLooking for '5C 6E 22 5C 72' (\\n\"\\r) in the file...")
search = bytes([0x5C, 0x6E, 0x22, 0x5C, 0x72])
pos2 = raw.find(search)
print("Found at byte: %d" % pos2)
if pos2 >= 0:
    print("Context: %s" % repr(raw[pos2-10:pos2+20]))
