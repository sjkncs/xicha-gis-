NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

print("File size: %d bytes" % len(raw))

# Find the problematic CR (0D) at end of line 3313
# This CR is NOT followed by LF, and it's at the end of a line

# Search for CR not followed by LF
found = False
for i in range(len(raw) - 1):
    if raw[i] == 0x0D and raw[i+1] != 0x0A:
        print("Found bare CR at byte %d" % i)
        print("Context: %s" % repr(raw[i-20:i+20]))
        
        # Check if this is at end of line 3313
        # The pattern should be: '   ],\r' at the end of a line
        # After the CR, there should be '\n   }\r\n ]\r\n'
        
        # Fix: Insert LF after this CR
        raw.insert(i + 1, 0x0A)
        found = True
        print("Fixed: Inserted LF after CR")
        break

if found:
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(raw)
    print("Saved!")
    
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
    print("No bare CR found")
