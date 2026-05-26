NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Try loading
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
    print("Error: %s at line %d" % (e.msg, e.lineno))
    print("pos: %d" % e.pos)
    
    # Count lines up to pos
    text = raw[:e.pos].decode('utf-8', errors='replace')
    line_num = text.count('\n') + 1
    col = len(text) - text.rfind('\n')
    print("Position is approximately line %d, column %d" % (line_num, col))
    
    # Show context
    lines = text.split('\n')
    for i in range(max(0, line_num-5), min(len(lines), line_num+2)):
        print("Line %d: %s" % (i+1, repr(lines[i][:80])))
