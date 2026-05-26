NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# Direct JSON parsing to find the problem
try:
    nb = json.loads(content)
    print("JSON is valid! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error at char %d: %s" % (e.pos, e))
    
    # Show context around error
    ctx = content[max(0, e.pos-200):e.pos+200]
    print("\n--- Context (repr) ---")
    print(repr(ctx))
    print("\n--- Context (decoded) ---")
    print(ctx)
    
    # Find which line/column
    before = content[:e.pos]
    ln = before.count('\n') + 1
    col = len(before) - before.rfind('\n') - 1
    print("\nError at line %d, col %d" % (ln, col))
    
    # Print surrounding lines
    all_lines = content.split('\n')
    print("\n--- Lines %d to %d ---" % (ln-3, ln+3))
    for i in range(max(0, ln-4), min(len(all_lines), ln+3)):
        print("Line %d: %s" % (i+1, repr(all_lines[i][:80])))
