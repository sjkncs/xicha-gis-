NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Line 3312 ends with '",' (proper comma)
# Line 3313 ends with just '"' (no comma)
# But line 3313 is NOT the last element - there are more after!
# So line 3313 SHOULD have a comma

# Fix: Add comma at end of line 3313
# Current: 22 0A (quote + LF)
# Should be: 22 2C 0A (quote + comma + LF)

# Find line 3313
lf_positions = [i for i, b in enumerate(raw) if b == 0x0A]
if len(lf_positions) >= 3313:
    line_start = lf_positions[3311] + 1  # after LF 3312
    line_end = lf_positions[3312]  # at LF 3313
    
    line_bytes = raw[line_start:line_end]
    print("Line 3313: %s" % repr(line_bytes))
    
    # Check last bytes
    print("Last 5 bytes: %s" % ' '.join('%02X' % b for b in line_bytes[-5:]))
    
    # Check if ends with quote
    if line_bytes[-1:] == b'"':
        print("Ends with quote - adding comma...")
        
        # Add comma after quote
        new_raw = raw[:line_end-1] + b',"' + raw[line_end-1:]
        
        with open(NOTEBOOK_PATH, 'wb') as f:
            f.write(new_raw)
        print("Fixed!")
        
        try:
            with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                nb = json.load(f)
            print("SUCCESS! %d cells" % len(nb['cells']))
        except json.JSONDecodeError as e:
            print("Error: %s at line %d" % (e.msg, e.lineno))
    else:
        print("Unexpected end: %s" % repr(line_bytes[-3:]))
