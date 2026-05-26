NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# The last source element has a trailing comma that shouldn't be there
# Current: '    "print(\'=\'*60)\\n"\\r",' <- comma after \r
# Should be: '    "print(\'=\'*60)\\n"\\r"' <- no comma (last element)

# Fix: Change \r", to \r"
search = bytes([0x5C, 0x72, 0x22, 0x2C])  # \r",
pos = raw.find(search)
print("Pattern \\r\", at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-20:pos+40]))
    
    # Remove comma
    new_raw = raw[:pos+3] + raw[pos+4:]
    
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
