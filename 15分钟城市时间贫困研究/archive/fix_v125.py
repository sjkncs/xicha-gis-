NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

# Method 1: text.split('\n')
lines = text.split('\n')
print("Method 1 (text.split('\\n')): Total lines: %d" % len(lines))
if len(lines) >= 3313:
    print("Line 3313: %s" % repr(lines[3312][:80]))

# Method 2: lf_positions
lf_positions = [i for i, c in enumerate(text) if c == '\n']
print("\nMethod 2 (lf_positions): Total LFs: %d" % len(lf_positions))
if len(lf_positions) >= 3312:
    l3313_start = lf_positions[3311] + 1
    l3313_end = lf_positions[3312]
    line_bytes = raw[l3313_start:l3313_end]
    line_text = line_bytes.decode('utf-8', errors='replace')
    print("Line 3313 (bytes %d-%d): %s" % (l3313_start, l3313_end, repr(line_text[:80])))

# Check if they match
print("\n=== Verifying JSON status ===")
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
