NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# First, try to load with json and see what happens
try:
    nb = json.loads(raw)
    print("SUCCESS! %d cells" % len(nb['cells']))
    sys.exit(0)
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))

# Get text
text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# The problem is around line 3313. Let me find what's WRONG by checking bracket counts
print("\n=== Finding the real error ===")

# Count brackets to find where things go wrong
depth = 0
in_str = False
escaped = False

for line_num, line in enumerate(lines, 1):
    for char in line:
        if not in_str:
            if char == '"':
                in_str = True
                escaped = False
        else:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_str = False
            elif char in '\n\r':
                # Error: unclosed string
                print("UNCLOSED STRING at line %d" % line_num)
                print("  Line: %s" % repr(line[:80]))
                break
    
    if not in_str:
        # Outside strings, count brackets
        for char in line:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
    
    # Show depth around error
    if 3310 <= line_num <= 3320:
        print("Line %d: depth=%d" % (line_num, depth))
