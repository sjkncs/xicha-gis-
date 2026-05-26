NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Find the REAL print('='*60) statement in raw bytes
search = b"print('='*60)"
pos = raw.find(search)
print("Found print('='*60) at raw byte %d" % pos)

# Get context around it
print("\n=== Context bytes %d-%d ===" % (pos-50, pos+80))
chunk = raw[pos-50:pos+80]
print(' '.join('%02X' % b for b in chunk))

# Decode this chunk
chunk_text = chunk.decode('utf-8', errors='replace')
print("\nDecoded: %s" % repr(chunk_text))

# Now find where this string starts in the source array
# Looking backwards from pos
print("\n=== Looking backwards for string start ===")
for i in range(pos, pos-200, -1):
    if i < 0:
        break
    if raw[i] == 0x22:  # Quote character
        print("Quote found at raw byte %d" % i)
        print("Context: %s" % ' '.join('%02X' % b for b in raw[i:i+30]))
        # Check if this is the start of the print statement
        start_chunk = raw[i:i+20]
        if b"print" in start_chunk:
            print("This is the print statement start!")
            break
        break

# Find the entire string for print('='*60)
# The string starts with "    " or "    "print('='*60)
# Let me find where this string starts
search2 = b'"    "print'
pos2 = raw.rfind(search2, 0, pos)
print("\nFound '\"    \"print' at raw byte %d" % pos2)
print("Context: %s" % ' '.join('%02X' % b for b in raw[pos2:pos+50]))

# The string content is from pos2+1 (after the opening quote) to pos (before the closing quote)
# But wait, there might be indentation...

# Let me try a different approach - find the \n before print
search3 = b'\\n"'
pos3 = raw.rfind(search3, 0, pos)
print("\nFound '\\n\"' at raw byte %d" % pos3)
print("Context: %s" % ' '.join('%02X' % b for b in raw[pos3:pos3+30]))
