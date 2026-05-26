NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Show lines 3318-3345
print("\n=== Full context lines 3318-3345 ===")
for i in range(3317, min(3345, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# Also show raw bytes around the error position
print("\n=== Bytes around error ===")
try:
    nb = json.loads(content)
except json.JSONDecodeError as e:
    pos = e.pos
    ln = content[:pos].count('\n') + 1
    print("Error at char %d, line %d: %s" % (pos, ln, e.msg))
    
    # Show bytes around error
    start = max(0, pos - 100)
    end = min(len(content), pos + 100)
    ctx = content[start:end]
    print("Context (repr):")
    print(repr(ctx))
    
    # Find which line is broken
    all_lines = content.split('\n')
    print("\nBroken line %d:" % ln)
    print(repr(all_lines[ln-1]))
