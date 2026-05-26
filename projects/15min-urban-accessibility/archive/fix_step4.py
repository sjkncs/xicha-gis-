NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')

# Apply our fix
correct_replacement = (
    '    "    \\"def load_api_config():\\n\\",\\n'
    '    "\\n\\",\\n'
    '    "    config = \\{\\}\\\\n\\",\\n'
)
lines[3347] = correct_replacement

fixed_content = '\n'.join(lines)

# Try to parse
try:
    nb = json.loads(fixed_content)
except json.JSONDecodeError as e:
    pos = e.pos
    ln = fixed_content[:pos].count('\n') + 1
    
    # Show exact character context
    print("Error at char %d, line %d: %s" % (pos, ln, e))
    
    # Show bytes around error
    chunk = fixed_content[pos-5:pos+30]
    print("\n--- Bytes around error ---")
    for i, c in enumerate(chunk):
        print("  offset %d (abs %d): %r" % (i, pos-5+i, c))
    
    # Which line is it?
    print("\n--- Line %d ---" % ln)
    print(repr(fixed_content.split('\n')[ln-1]))
    print("\n--- Line %d ---" % (ln+1))
    print(repr(fixed_content.split('\n')[ln]))
    
    # The error says "Expecting ',' delimiter" at col 46 of line 3348
    # But our line 3348 has 82 chars - so which line?
    print("\n--- Lines 3345 to 3355 ---")
    for i in range(3344, min(3355, len(lines))):
        print("Line %d (idx %d): %s" % (i+1, i, repr(lines[i][:80])))
