NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Find the error position
try:
    nb = json.loads(content)
except json.JSONDecodeError as e:
    print("Error at char %d: %s" % (e.pos, e))
    ln = content[:e.pos].count('\n') + 1
    col = e.pos - content.rfind('\n', 0, e.pos) - 1
    print("Line %d, col %d" % (ln, col))
    
    # Show lines 3346-3352 (1-indexed)
    lines = content.split('\n')
    print("\n--- Lines 3345 to 3355 ---")
    for i in range(3344, min(3355, len(lines))):
        print("Line %d (idx %d): %s" % (i+1, i, repr(lines[i])))
    
    # Show exact bytes around error
    print("\n--- Exact bytes around error (chars %d to %d) ---" % (e.pos-20, e.pos+50))
    ctx = content[e.pos-20:e.pos+50]
    print("  chars:", list(ctx))
    print("  repr:", repr(ctx))
    
    # Count what's before and after the error in the current line
    line_start = content.rfind('\n', 0, e.pos) + 1
    line_content = content[line_start:line_start+200]
    print("\n--- Full line %d from char %d ---" % (ln, line_start))
    print("  repr:", repr(line_content))
