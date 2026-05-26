NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# ================================================================
# The problematic line 3348 (0-indexed) in the file contains
# 3 merged source entries that break JSON parsing:
#
# The broken line is:
#     "    \"def load_api_config():\n\",\n\",    "    config = \{\}\n\",\n",
#
# It should be 3 separate JSON string entries:
#     "    \"def load_api_config():\n\" ,
#     "\n" ,
#     "    config = \{\}\n\" ,
#
# I need to write these as proper JSON strings.
# In the JSON file (which is itself text), each backslash is \ and each quote is "
#
# Entry 1: "    \"def load_api_config():\n\" ,
# Entry 2: "\n" ,
# Entry 3: "    config = \{\}\n\" ,
# ================================================================

# Build the exact replacement string
# In Python string: \\ = one backslash \  \" = one quote "
entry1 = '    "    \\"def load_api_config():\\n\\",\\n'
entry2 = '    "\\n\\",\\n'
entry3 = '    "    config = \\{\\}\\\\n\\",'

broken = '    "\\    \\"def load_api_config():\\n\\",\\n\\",    \\"    config = \\{\\}\\\\n\\",\\n",'

print("Broken line:", repr(broken))
print("Entry 1:", repr(entry1))
print("Entry 2:", repr(entry2))
print("Entry 3:", repr(entry3))

if broken in content:
    content = content.replace(broken, entry1 + entry2 + entry3, 1)
    print("\nFIX applied!")
else:
    print("\nPattern not found - checking what exists...")
    idx = content.find('load_api_config')
    if idx >= 0:
        print("Found at idx %d" % idx)
        # Show 200 chars around it
        ctx = content[idx-50:idx+200]
        print("Context:", repr(ctx))
        # Find line number
        ln = content[:idx].count('\n') + 1
        print("This is around line %d" % ln)

print("\n=== Validating JSON ===")
try:
    nb = json.loads(content)
    print("SUCCESS! %d cells" % len(nb['cells']))
    for i, cell in enumerate(nb['cells']):
        ct = cell['cell_type']
        src = ''.join(cell['source'][:1])
        preview = src[:50].replace('\n', '\\n')
        print("  Cell %d: %s -> %s" % (i, ct, preview))
    with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print("\nSaved!")
except json.JSONDecodeError as e:
    print("Still broken at char %d: %s" % (e.pos, e))
    ln = content[:e.pos].count('\n') + 1
    print("Line %d: %s" % (ln, repr(content.split('\n')[ln-1][:100])))
    ctx = content[max(0, e.pos-100):e.pos+200]
    print("Context:", repr(ctx))
