NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read raw bytes
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find line 3313 by counting newlines
line_count = 0
pos = 0
for i, byte in enumerate(raw):
    if byte == 0x0A:  # LF
        line_count += 1
        if line_count == 3313:
            pos = i + 1
            break

print("\nStart of line 3313 at byte: %d" % pos)

# Show 500 bytes from there
if pos > 0:
    area = raw[pos:pos+500]
    print("\nRaw bytes:")
    for i in range(0, len(area), 32):
        chunk = area[i:i+32]
        hex_part = ' '.join('%02X' % b for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print('%04X: %-96s | %s' % (pos+i, hex_part, ascii_part))
    
    print("\nDecoded:")
    print(repr(area.decode('utf-8', errors='replace')))

# Find "cells": [ position
cells_idx = raw.find(b'"cells": [')
print("\n\n'cells': [' at byte: %d" % cells_idx)

# Find the end of the file
print("\n\nLast 200 bytes:")
print(' '.join('%02X' % b for b in raw[-200:]))
print(repr(raw[-200:].decode('utf-8', errors='replace')))
