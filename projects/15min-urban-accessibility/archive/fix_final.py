NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Show lines 3318-3345
print("\n=== Lines 3318 to 3345 ===")
for i in range(3317, min(3345, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# ================================================================
# STRATEGY: 
# 1. Keep line 3321: closes Section 13 markdown cell
# 2. Keep line 3322: opens Section 14 code cell  
# 3. Remove lines 3323-3329: broken Section 13 code cell with malformed source
# 4. Replace with: proper close of source array + close of Section 14 code cell
# 5. Keep line 3330: opens Section 9 cell
#
# The correct replacement for lines 3323-3329 (7 lines):
#   "  ],\n"  -> close source array
#   " },\n"   -> close cell
#   " {\n"    -> open next cell
# ================================================================

# Build correct replacement strings
REPLACE_3323 = '    "  ],\\n",' + '\n'   # close source array
REPLACE_3329 = '    " },\\n",' + '\n'    # close cell
REPLACE_3330 = '    " {\\n",'             # open next cell (Section 9)

# But this is 3 separate lines that need to be inserted
# So we replace line 3323 with all 3 lines, and remove 3324-3329
lines_to_insert = (
    '    "  ],\\n",\n'   # close source array
    '    " },\\n",\n'    # close Section 14 cell
    '    " {\\n",\n'     # open Section 9 cell
)

print("\n=== Lines to insert ===")
for l in lines_to_insert.split('\n')[:-1]:
    print("  ", repr(l))

# Remove lines 3323-3329 (indices 3322-3328), insert the 3 new lines at position 3322
old_lines = lines[3322:3329]  # lines 3323-3329
print("\n=== Removing lines 3323-3329 ===")
for i, l in enumerate(old_lines):
    print("  Line %d: %s" % (3323+i, repr(l[:60])))

# Replace
new_lines = lines[:3322] + [lines_to_insert] + lines[3329:]

print("\n=== After replacement ===")
print("New total lines:", len(new_lines))
print("\nLines around insertion point:")
for i in range(3319, min(3330, len(new_lines))):
    print("  Line %d: %s" % (i+1, repr(new_lines[i][:80])))

fixed_content = '\n'.join(new_lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(fixed_content)
print("\nSaved!")

# Validate
print("\n=== Validating JSON ===")
try:
    nb = json.loads(fixed_content)
    print("SUCCESS! %d cells" % len(nb['cells']))
    for i, cell in enumerate(nb['cells']):
        ct = cell['cell_type']
        src = ''.join(cell['source'][:1])
        preview = src[:60].replace('\n', '\\n')
        print("  Cell %d: %s -> %s" % (i, ct, preview))
except json.JSONDecodeError as e:
    pos = e.pos
    ln = fixed_content[:pos].count('\n') + 1
    print("Error at line %d: %s" % (ln, e))
    print("Line %d: %s" % (ln, repr(fixed_content.split('\n')[ln-1][:100])))
    ctx = fixed_content[max(0, e.pos-100):e.pos+100]
    print("Context:", repr(ctx))
