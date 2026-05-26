NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Line 3313 should be:
# '    "print(\'=\'*60)\\n",\r'
# But it's missing the opening quote!
# Current: '    "print(\'=\'*60)\\n"\\r,'
# Fix: Add opening quote at start

# The pattern to fix: starts with spaces, print, but no opening quote
# b'    print(\\'=\\'*60)\\'\\n"\\r,'
# Should be: b'    "print(\\'=\\'*60)\\'\\n",\\r'

# Find the line: it starts with 4 spaces followed by 'print('='*60)'
search = b'    print(\'=\'*60)'
pos = raw.find(search)
print("Found at byte: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-5:pos+50]))
    
    # The fix: Add " after the 4 spaces
    # b'    print(' -> b'    "print('
    new_raw = raw.replace(b'    print(\'=\'*60)', b'    "print(\'=\'*60)', 1)
    
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
