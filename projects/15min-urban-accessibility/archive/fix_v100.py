NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Try to parse
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Find the actual line boundaries
    lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
    
    # Line N in text terms is at LF[N-2] to LF[N-1] in the LF array
    err_line = e.lineno
    
    # Line starts after LF[err_line - 2] and ends at LF[err_line - 1]
    if err_line >= 2:
        line_start = lf_positions[err_line - 2] + 1
        line_end = lf_positions[err_line - 1]
        line_bytes = raw[line_start:line_end]
        print("\nActual error line %d: bytes %d-%d (%d bytes)" % (err_line, line_start, line_end, len(line_bytes)))
        print("Hex: %s" % ' '.join('%02X' % b for b in line_bytes))
        print("Text: %s" % repr(line_bytes))
    
    # Check the PREVIOUS line
    if err_line >= 2:
        prev_line = err_line - 1
        prev_start = lf_positions[prev_line - 2] + 1
        prev_end = lf_positions[prev_line - 1]
        prev_bytes = raw[prev_start:prev_end]
        print("\nPrevious line %d: bytes %d-%d (%d bytes)" % (prev_line, prev_start, prev_end, len(prev_bytes)))
        print("Hex: %s" % ' '.join('%02X' % b for b in prev_bytes))
        print("Text: %s" % repr(prev_bytes))
    
    # Check the NEXT line
    if err_line < len(lf_positions):
        next_line = err_line + 1
        next_start = lf_positions[next_line - 1] + 1
        next_end = lf_positions[next_line] if next_line < len(lf_positions) else len(raw)
        next_bytes = raw[next_start:next_end]
        print("\nNext line %d: bytes %d-%d (%d bytes)" % (next_line, next_start, next_end, len(next_bytes)))
        print("Hex: %s" % ' '.join('%02X' % b for b in next_bytes))
        print("Text: %s" % repr(next_bytes))
