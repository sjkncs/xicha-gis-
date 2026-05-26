NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Python json.loads counts newlines differently
# Let me use json.loads internals to find the exact position

# Try loading and catch error
try:
    json.loads(raw)
except json.JSONDecodeError as e:
    print("Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    print("pos: %d" % e.pos)
    
    # Get text up to error position
    text_before = raw[:e.pos].decode('utf-8', errors='replace')
    lines = text_before.split('\n')
    print("\nLast 10 lines of text before error:")
    for i in range(max(0, len(lines)-10), len(lines)):
        print("  Line %d: %s" % (i+1, repr(lines[i])))
    
    # The error is "Expecting ',' delimiter" - JSON expects comma after element
    # but found something else (like closing bracket or string start)
    # This usually means a string is missing its closing quote

print("\n\nSearching for problematic patterns in source...")

# Search for patterns that indicate broken strings
# A string value should be: "content\n" with proper escaping
# Broken pattern: "content\n without closing quote

# Look for: backslash-n then newline character (not escaped)
# Pattern in bytes: 5C 6E (backslash+n) followed by 0A or 0D (actual newline)

search = b'\\n"\n'
pos = raw.find(search)
if pos >= 0:
    print("\nFound \\n\" followed by LF (unclosed string?):")
    print("  byte %d: %s" % (pos, repr(raw[pos-20:pos+40])))
