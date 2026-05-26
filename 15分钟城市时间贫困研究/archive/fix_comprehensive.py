NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines before fix:", len(lines))

# ================================================================
# REMOVAL: Lines 3328-3391 (corrupted Section 13 code inside 
#          Section 10's source array, plus the extra ] close)
#
# Before (after line 3327 = source array opening):
#   Line 3328-3390: corrupted Section 13 code
#   Line 3391: '   ]' <- WRONG: extra close (malformed array) 
#   Line 3392: '   ]' <- close of Section 10's source array
#   Line 3393: '  },' <- close of Section 10 cell
#   Line 3394: '  {' <- open Section 9 cell
#
# After removal (keeps lines 3327, 3392, 3393, 3394...):
#   Line 3327: '    "  \"source\": [' <- Section 10's source array opening (EMPTY)
#   Line 3328: '   ]' <- close of Section 10's source array (NOW EMPTY ARRAY)
#   Line 3329: '  },' <- close of Section 10 cell
#   Line 3330: '  {' <- open Section 9 cell
# ================================================================

# Remove lines 3328-3391 (0-indexed: 3327-3390)
# Keep lines 0-3327 (up to source array open) + lines 3391 onwards
lines_0_to_3327 = lines[:3327]  # Lines 1-3327 (source array opening preserved)
lines_3392_onwards = lines[3391:]  # Lines 3392+ (both ] and Section 9 start)

new_lines = lines_0_to_3327 + lines_3392_onwards

print("\nAfter removal:")
print("  Kept lines 1-3327 (0-indexed 0-3326)")
print("  Removed lines 3328-3391 (corrupted Section 13 code)")
print("  Kept lines 3392+ (now at positions 3327+)")
print("  New total lines:", len(new_lines))

print("\n=== Verify structure ===")
print("  Line 3327:", repr(new_lines[3326][:80]))
print("  Line 3328:", repr(new_lines[3327][:80]))
print("  Line 3329:", repr(new_lines[3328][:80]))
print("  Line 3330:", repr(new_lines[3329][:80]))
print("  Line 3331:", repr(new_lines[3330][:80]))
print("  Line 3332:", repr(new_lines[3331][:80]))

# Save
fixed_content = '\n'.join(new_lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(fixed_content)
print("\nSaved!")

# Validate JSON
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
    print("JSON error at line %d: %s" % (ln, e))
    ctx = fixed_content.split('\n')[ln-1:ln+2]
    for l in ctx:
        print("  %s" % repr(l))
