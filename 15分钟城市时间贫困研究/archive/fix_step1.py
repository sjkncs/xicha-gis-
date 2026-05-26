NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json, re

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# ================================================================
# FIX 1: Line 3348 - the merged triple-entry causing \n" escape error
# Raw line content:
# '    "\\    \\"def load_api_config():\\n\\",\\n\\",    \\"    config = \\{\\}\\\\n\\",\\n",'
# 
# This should be 3 separate entries:
#     "    \\"def load_api_config():\\n\\",
#     "\\n",
#     "    \\"    config = \\{\\}\\\\n\\",
# ================================================================
OLD = '    "\\    \\"def load_api_config():\\n\\",\\n\\",    \\"    config = \\{\\}\\\\n\\",\\n",'
NEW = '    "    \\"def load_api_config():\\n\\",\\n    "\\n\\",\\n    "    config = \\{\\}\\\\n\\",'

if OLD in content:
    content = content.replace(OLD, NEW, 1)
    print("FIX 1 applied: Split merged line 3348")
else:
    print("FIX 1: Pattern not found!")
    # Find what's actually there around load_api_config
    idx = content.find('load_api_config')
    if idx >= 0:
        print("  Context:", repr(content[idx-50:idx+150]))

# ================================================================
# Now verify JSON
# ================================================================
print("\n=== Validating JSON ===")
try:
    nb = json.loads(content)
    print("SUCCESS! %d cells" % len(nb['cells']))
    print("\nCell structure:")
    for i, cell in enumerate(nb['cells']):
        ct = cell['cell_type']
        src = ''.join(cell['source'][:1])
        preview = src[:50].replace('\n', '\\n').replace('\\n\\', '')
        print("  Cell %d: %s -> %s" % (i, ct, preview))
    
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\nSaved successfully!")
    
except json.JSONDecodeError as e:
    print("Still broken at char %d: %s" % (e.pos, e))
    ln = content[:e.pos].count('\n') + 1
    col = e.pos - content.rfind('\n', 0, e.pos)
    print("Line %d, col %d: %s" % (ln, col, repr(content.split('\n')[ln-1][:100])))
    
    # Show context
    ctx = content[max(0, e.pos-100):e.pos+200]
    print("\nContext:", repr(ctx))
