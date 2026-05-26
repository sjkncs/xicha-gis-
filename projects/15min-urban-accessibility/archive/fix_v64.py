NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Check current state of line 3313
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
if len(lf_positions) >= 3313:
    line_start = lf_positions[3311] + 1
    line_end = lf_positions[3312]
    line_bytes = raw[line_start:line_end]
    print("Line 3313: %s" % repr(line_bytes))
    print("Last 10 bytes: %s" % ' '.join('%02X' % b for b in line_bytes[-10:]))
    
    # Now parse and show exact error
    try:
        nb = json.loads(raw)
        print("SUCCESS!")
    except json.JSONDecodeError as e:
        print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
        print("Pos: %d" % e.pos)
        
        # Show context
        text = raw[:e.pos].decode('utf-8', errors='replace')
        lines = text.split('\n')
        print("\nLast 3 lines:")
        for i in range(max(0, len(lines)-3), len(lines)):
            print("  Line %d: %s" % (i+1, repr(lines[i][:100])))
