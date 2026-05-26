NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Track the bracket nesting depth as we parse line by line
depth = 0
in_string = False
escaped = False
errors = []

for line_num, line in enumerate(lines, 1):
    for col_num, char in enumerate(line, 1):
        if not in_string:
            if char == '"':
                in_string = True
                escaped = False
            elif char in '{[}],\n\r':
                # Track depth changes outside strings
                pass
        else:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
            elif char in '\n\r':
                # Unclosed string!
                errors.append((line_num, col_num, 'Unclosed string'))
                in_string = False
                escaped = False
    
    # After processing line, check for bracket issues
    # Count brackets in the line (outside strings)
    stripped = ''
    in_str = False
    esc = False
    for char in line:
        if not in_str:
            if char == '"':
                in_str = True
                esc = False
            elif char not in ' \t\r\n':
                stripped += char
        else:
            if esc:
                esc = False
            elif char == '\\':
                esc = True
            elif char == '"':
                in_str = False
    
    # Now count brackets in stripped
    for ch in stripped:
        if ch == '{' or ch == '[':
            depth += 1
        elif ch == '}' or ch == ']':
            depth -= 1
    
    if line_num >= 3310 and line_num <= 3320:
        print("Line %d: depth=%d, stripped='%s'" % (line_num, depth, stripped))

print("\n=== Checking if brackets are balanced at end ===")
print("Final depth: %d (should be 0)" % depth)

# Try parsing
try:
    nb = json.loads(text)
    print("\nSUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("\nError: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    print("Text at error: %s" % repr(lines[e.lineno-1] if e.lineno <= len(lines) else 'N/A'))
