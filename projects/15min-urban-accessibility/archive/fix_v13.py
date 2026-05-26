NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# From the hex dump:
# Current: 20 20 20 20 22 20 7D 2C 0D 0A 20 20 20 20 20 5D 2C 0D 0A
# = 4-space " 2-space },\r\n 5-space ],\r\n
# Should be: 20 20 22 20 7D 2C 0D 0A 5D 2C 0D 0A
# = 2-space " 2-space },\r\n 2-space ],\r\n

BROKEN = b'    " },\r\n     ],'
FIXED = b'  },\r\n],'

pos = raw.find(BROKEN)
print("Broken pattern at byte: %d" % pos)

if pos >= 0:
    print("Found! Applying fix...")
    print("Context: %s" % repr(raw[pos-10:pos+len(BROKEN)+20]))
    new_raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
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
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found. The file may have already been fixed.")
    # Try JSON load to verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("JSON is valid! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("But JSON is still broken: %s at line %d" % (e.msg, e.lineno))
