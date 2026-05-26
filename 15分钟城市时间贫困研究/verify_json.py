NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Try JSON load
try:
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    print("SUCCESS! JSON is valid!")
    print("Number of cells: %d" % len(nb['cells']))
    for i, cell in enumerate(nb['cells']):
        cell_type = cell.get('cell_type', 'unknown')
        # Get first line of source
        src = cell.get('source', [])
        if isinstance(src, list):
            first_line = src[0].strip()[:60] if src else '(empty)'
        else:
            first_line = str(src)[:60]
        print("  Cell %d: %s | %s" % (i, cell_type, first_line))
except json.JSONDecodeError as e:
    print("JSON ERROR: %s" % e)
    print("At line %d, col %d, pos %d" % (e.lineno, e.colno, e.pos))
    
    # Show context around error
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    for i in range(max(0, e.lineno-5), min(len(lines), e.lineno+3)):
        marker = ">>> " if i+1 == e.lineno else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
