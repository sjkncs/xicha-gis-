NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find line 133 in raw bytes
text = raw.decode('utf-8', errors='replace')
lf_positions = [i for i, c in enumerate(text) if c == '\n']

# Line 133 (0-indexed 132) starts after LF[131] and ends at LF[132]
l133_start = lf_positions[131] + 1
l133_end = lf_positions[132]

print("Line 133 bytes (%d-%d):" % (l133_start, l133_end))
line_bytes = raw[l133_start:l133_end]
print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
print("Text: %s" % repr(line_bytes.decode('utf-8', errors='replace')))

# Line 133 should end with: ]\r\n
# But it should have a comma after ]: ]\r\n
# Actually in JSON, key-value pairs should be separated by commas
# So line 133 should end with: ],\r\n

# Current: 5D 0D 0A = ]\r\n
# Should be: 5D 2C 0D 0A = ],\r\n

if line_bytes[-3:] == b']\r\n':
    print("\nFound closing ] without comma")
    # Add comma
    line_bytes = line_bytes[:-3] + b'],\r\n'
    print("Fixed to: %s" % ' '.join('%02X' % b for b in line_bytes))
    
    # Update raw
    raw = raw[:l133_start] + line_bytes + raw[l133_end:]
    
    # Save
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("Saved.")
    
    # Test
    try:
        nb = json.loads(raw)
        print("\nSUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
else:
    print("Pattern not found, checking actual bytes...")
    print("Last 4 bytes: %s" % ' '.join('%02X' % b for b in line_bytes[-4:]))
