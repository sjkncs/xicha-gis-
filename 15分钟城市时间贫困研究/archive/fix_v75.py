NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("=== Lines 3300-3330 ===")
for i in range(3299, min(3330, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

print("\n=== Parsing with trace ===")
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Find cell boundaries near the error
    print("\n=== Finding cell boundaries ===")
    for cell_idx in range(len(lines)):
        line = lines[cell_idx]
        if '"cell_type":' in line:
            print("Line %d: %s" % (cell_idx+1, repr(line.strip())))
        if '"source": [' in line:
            print("Line %d: SOURCE ARRAY START - %s" % (cell_idx+1, repr(line.strip())))
        if line.strip() == '],' or line.strip() == '],\\' or line.strip() == '"],':
            print("Line %d: POSSIBLE SOURCE END - %s" % (cell_idx+1, repr(line.strip())))
