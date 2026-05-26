NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read the file
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')

print("Checking JSON validity...")
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Find and display the problematic line
    lines = text.split('\n')
    if e.lineno <= len(lines):
        print("\nProblematic line %d:" % e.lineno)
        print("  %s" % repr(lines[e.lineno-1]))
        
        # Also show surrounding lines
        if e.lineno > 1:
            print("Line %d: %s" % (e.lineno-1, repr(lines[e.lineno-2])))
        if e.lineno <= len(lines):
            print("Line %d: %s" % (e.lineno, repr(lines[e.lineno-1])))
        if e.lineno < len(lines):
            print("Line %d: %s" % (e.lineno+1, repr(lines[e.lineno])))
