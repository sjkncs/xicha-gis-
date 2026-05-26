NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Current bytes: 22 5C 72 2C 0A 20 20 20 5D 2C
# = " \ r , LF spaces ] ,
# Fix: Remove comma = 22 5C 72 0A 20 20 20 5D 2C
# = " \ r LF spaces ] , 

old = bytes([0x22, 0x5C, 0x72, 0x2C, 0x0A, 0x20, 0x20, 0x20, 0x5D, 0x2C])
new = bytes([0x22, 0x5C, 0x72, 0x0A, 0x20, 0x20, 0x20, 0x5D, 0x2C])

pos = raw.find(old)
print("Pattern at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-30:pos+40]))
    
    new_raw = raw.replace(old, new, 1)
    
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
    print("Pattern not found")
