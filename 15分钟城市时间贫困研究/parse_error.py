NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Try parsing and get detailed error
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s" % e.msg)
    print("Line: %d, Col: %d" % (e.lineno, e.colno))
    print("Pos: %d" % e.pos)
    
    # Get text before error
    text = raw[:e.pos].decode('utf-8', errors='replace')
    lines = text.split('\n')
    last_line = lines[-1]
    
    print("\nLast line before error:")
    print("  %s" % repr(last_line))
    print("  %d chars" % len(last_line))
    
    # Show character at error position in last line
    if e.colno <= len(last_line):
        print("\nChar at error position (col %d): 0x%02X = '%s'" % (
            e.colno, ord(last_line[e.colno-1]), last_line[e.colno-1:e.colno+10]))
    
    # Check for common issues
    if '"\\r"' in last_line[:e.colno]:
        print("\nFound \\r\" pattern - string may not be properly closed")
    if last_line[e.colno-1] == ']':
        print("\nAt ']' - might be array closing issue")
