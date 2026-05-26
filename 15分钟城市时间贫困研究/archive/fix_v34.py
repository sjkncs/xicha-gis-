NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Try to parse and get error position
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

try:
    nb = json.loads(raw)
    print("JSON is valid!")
except json.JSONDecodeError as e:
    print("Error: %s" % e.msg)
    print("At line %d, col %d, pos %d" % (e.lineno, e.colno, e.pos))
    
    # Show what character is at pos
    if e.pos < len(raw):
        ctx_start = max(0, e.pos - 50)
        ctx_end = min(len(raw), e.pos + 50)
        ctx = raw[ctx_start:ctx_end]
        print("\nContext around error (bytes %d-%d):" % (ctx_start, ctx_end))
        print("Hex: %s" % ' '.join('%02X' % b for b in ctx))
        print("Decoded: %s" % repr(ctx.decode('utf-8', errors='replace')))
    
    # Find line number of error
    lines_before = raw[:e.pos].count(b'\n')
    print("\nError is at LF #%d (line %d in 1-indexed)" % (lines_before, lines_before + 1))
    
    # Show 5 lines around the error
    print("\n\nLines around error:")
    all_lines = raw.decode('utf-8', errors='replace').split('\n')
    for i in range(max(0, lines_before-2), min(len(all_lines), lines_before+3)):
        marker = ">>> " if i == lines_before else "    "
        print("%s%d: %s" % (marker, i+1, repr(all_lines[i])))
