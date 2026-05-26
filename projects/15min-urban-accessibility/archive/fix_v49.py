NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The structure is:
# "print('='*60)\n"\r<LF><spaces>]<comma>
# In bytes: 5C 6E 22 5C 72 0A 20 20 20 5D 2C

# The issue: After the string closes with "\r, there's a lone LF
# which should be: ,\n (comma + LF)

# Fix: Change 5C 72 0A to 5C 72 2C 0A
# (add comma after \r, before LF)

# Search for the pattern: \r followed by LF
search = bytes([0x5C, 0x72, 0x0A])
pos = raw.find(search)
print("Pattern \\r<LF> at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-20:pos+40]))
    
    # Check what's after LF
    if pos + 3 < len(raw):
        after_lf = raw[pos+3:pos+8]
        print("After LF: %s" % repr(after_lf))
        
        # If after LF is spaces then ], we need to add comma
        if after_lf[:3] == bytes([0x20, 0x20, 0x20]) and len(raw) > pos + 6:
            if raw[pos+6] == 0x5D:  # ]
                print("Found pattern! Adding comma after \\r...")
                
                # Insert comma at position after \r
                new_raw = raw[:pos+2] + b',' + raw[pos+2:]
                
                with open(NOTEBOOK_PATH, 'wb') as f:
                    f.write(new_raw)
                print("Fixed!")
                
                # Verify
                try:
                    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                        nb = json.load(f)
                    print("SUCCESS! %d cells" % len(nb['cells']))
                    
                    for i, cell in enumerate(nb['cells']):
                        cell_type = cell.get('cell_type', 'unknown')
                        src = cell.get('source', [])
                        if isinstance(src, list):
                            first_line = src[0].strip()[:60] if src else '(empty)'
                        else:
                            first_line = str(src)[:60]
                        print("  Cell %d: %s | %s" % (i, cell_type, first_line))
                        
                except json.JSONDecodeError as e:
                    print("Still broken: %s at line %d" % (e.msg, e.lineno))
            else:
                print("Not the right pattern. After spaces: %02X" % raw[pos+6] if pos+6 < len(raw) else "EOF")
else:
    print("Pattern not found")
