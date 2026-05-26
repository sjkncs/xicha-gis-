NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
line = lines[3347]  # 0-indexed

print("BEFORE:", repr(line))

# Build the correct replacement
# Split the broken line into 3 proper JSON string entries
correct_replacement = (
    '    "    \\"def load_api_config():\\n\\",\\n'
    '    "\\n\\",\\n'
    '    "    config = \\{\\}\\\\n\\",\\n'
)

print("AFTER: ", repr(correct_replacement))

# Also fix the lines that follow - they might also have the same issue
# Check lines 3349-3354
print("\n=== Checking subsequent lines ===")
for i in range(3348, 3360):
    if i < len(lines):
        l = lines[i]
        print("Line %d: %s" % (i+1, repr(l[:80])))

# Apply the fix
lines[3347] = correct_replacement

fixed_content = '\n'.join(lines)

print("\n=== Validating JSON ===")
try:
    nb = json.loads(fixed_content)
    print("SUCCESS! %d cells" % len(nb['cells']))
    for i, cell in enumerate(nb['cells']):
        ct = cell['cell_type']
        src = ''.join(cell['source'][:1])
        preview = src[:60].replace('\n', '\\n')
        print("  Cell %d: %s -> %s" % (i, ct, preview))
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    print("\nSaved!")
except json.JSONDecodeError as e:
    print("Still broken at char %d: %s" % (e.pos, e))
    ln = fixed_content[:e.pos].count('\n') + 1
    print("Line %d: %s" % (ln, repr(fixed_content.split('\n')[ln-1][:100])))
    ctx = fixed_content[max(0, e.pos-50):e.pos+100]
    print("Context:", repr(ctx))
