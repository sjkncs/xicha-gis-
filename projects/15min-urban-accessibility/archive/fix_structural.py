NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# PROBLEM 1: Line 3320 (Section 13 markdown header)
# Current: '    "   \\"<a id=\\'13\\'></a>---## 13. 街景感知与AI感知评分\\"  ]\\n",'
# The ']' is INSIDE the string, not closing the array
# FIX: Move the ] outside the string
# ================================================================
OLD_3320 = '    "   \\"<a id=\'13\'></a>---## 13. 街景感知与AI感知评分\\"  ]\\n",'
NEW_3320 = ('    "   \\"<a id=\'13\'></a>---## 13. 街景感知与AI感知评分\\"\\n",\n'
            '    "  ]\\n",\n'
            '    " },\n",')

print("Line 3320 before:", repr(lines[3319]))
print("NEW_3320:", repr(NEW_3320))

# ================================================================
# PROBLEM 2: Lines 3323-3330 (Section 13 code cell with empty/broken source)
# Current structure:
#   Line 3323: "  \\"cell_type\\": \\"code\\",
#   Line 3324: "  \\"execution_count\\": null,
#   Line 3325: "  \\"metadata\\": {},
#   Line 3326: "  \\"outputs\\": [],
#   Line 3327: "  \\"source\\": [
#   Line 3328: '   ]'
#   Line 3329: '  },'
#   Line 3330: '  {'
# This is malformed - the source array has only a ] but no content
# FIX: Remove this entire broken cell (it's a leftover from Section 13 attempt)
# ================================================================

print("\nLine 3323:", repr(lines[3322]))
print("Line 3324:", repr(lines[3323]))
print("Line 3325:", repr(lines[3324]))
print("Line 3326:", repr(lines[3325]))
print("Line 3327:", repr(lines[3326]))
print("Line 3328:", repr(lines[3327]))
print("Line 3329:", repr(lines[3328]))
print("Line 3330:", repr(lines[3329]))

# ================================================================
# PLAN:
# 1. Fix line 3320 - properly close the Section 13 header cell's source array
# 2. Remove lines 3323-3329 (the broken Section 13 code cell stub)
# 3. Keep line 3330 ('  {') which starts Section 9 cell
# ================================================================

# Apply fixes
# Step 1: Fix line 3320
lines[3319] = NEW_3320

# Step 2: Remove lines 3323-3329 (broken code cell, indices 3322-3328)
# After fix, line 3320 becomes 3 lines, so:
# Original line 3323 (idx 3322) -> remove
# ...
# Original line 3329 (idx 3328) -> remove
# Original line 3330 (idx 3329) -> '  {' starts Section 9

# Remove indices 3322-3328 (7 lines)
removed = lines[3322:3329]  # lines 3323-3329
print("\nRemoving lines 3323-3329:")
for r in removed:
    print("  ", repr(r[:80]))

# Rebuild: keep 0-3321, skip 3322-3328, keep 3329+
lines = lines[:3322] + lines[3329:]

print("\nAfter fix:")
print("New total lines:", len(lines))
print("Line 3322:", repr(lines[3321][:80]))
print("Line 3323:", repr(lines[3322][:80]))
print("Line 3324:", repr(lines[3323][:80]))
print("Line 3325:", repr(lines[3324][:80]))
print("Line 3326:", repr(lines[3325][:80]))

fixed_content = '\n'.join(lines)
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
