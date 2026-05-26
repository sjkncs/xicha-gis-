NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Check bytes around line 3313
pos = 166400
chunk = raw[pos:pos+80]
print("Bytes %d-%d:" % (pos, pos+len(chunk)))
print("Hex: %s" % ' '.join('%02X' % b for b in chunk))
print()

# Specifically check: is there a comma after \\r"?
# Bytes: ...5C 72 22 2C 0D 0A... = \r " , CR LF
# vs: ...5C 72 22 0D 0A... = \r " CR LF

search1 = bytes([0x5C, 0x72, 0x22, 0x2C, 0x0D])  # \r",,
pos1 = raw.find(search1)
print("Pattern \\r\",, at byte: %d" % pos1)

search2 = bytes([0x5C, 0x72, 0x22, 0x2C, 0x0A])  # \r",LF
pos2 = raw.find(search2)
print("Pattern \\r\",LF at byte: %d" % pos2)

search3 = bytes([0x5C, 0x72, 0x22, 0x0D])  # \r"CR
pos3 = raw.find(search3)
print("Pattern \\r\"CR at byte: %d" % pos3)

search4 = bytes([0x5C, 0x72, 0x22, 0x0A])  # \r"LF
pos4 = raw.find(search4)
print("Pattern \\r\"LF at byte: %d" % pos4)

# Show context of pos4 if found
if pos4 >= 0:
    print("\nContext at \\r\"LF:")
    print("  %s" % repr(raw[pos4-30:pos4+40]))
