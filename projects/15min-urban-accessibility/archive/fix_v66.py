NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Check current state
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
if len(lf_positions) >= 3313:
    line_start = lf_positions[3311] + 1
    line_end = lf_positions[3312]
    line_bytes = raw[line_start:line_end]
    print("Line 3313: %s" % repr(line_bytes))
    print("Last 15 bytes: %s" % ' '.join('%02X' % b for b in line_bytes[-15:]))

# Try parsing
try:
    nb = json.loads(raw)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # The error is at col 22, line 3313
    # Line 3313 in text terms starts with spaces, print, etc.
    # Let me check character at col 22
    
    text = raw.decode('utf-8', errors='replace')
    lines = text.split('\n')
    
    if len(lines) >= 3313:
        line3313 = lines[3312]
        print("\nLine 3313 (text):")
        print("  %s" % repr(line3313))
        print("\nCol 22 char:")
        if len(line3313) >= 22:
            print("  Char at col 22: 0x%04X = '%s'" % (ord(line3313[21]), line3313[21]))
