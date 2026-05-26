NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines: %d" % len(lines))

# Show context
print("\nLines 3312-3330:")
for i in range(3311, 3330):
    print("%d: %s" % (i+1, repr(lines[i])))

# The problem: Line 3314 is a string that contains literal "  ]\n",
# instead of actually closing the source array with ],
# And line 3315 is a string that contains literal " },\n",
# instead of actually closing the cell with },

# Fix strategy: 
# Line 3314 should be: '   ],\n' (closes source array)
# Line 3315 should be: '  },\n' (closes cell object)
# Line 3316 should be: empty (line break)

# But actually looking more carefully, the issue is these are INSIDE the source array
# The source array opened at line 3072
# It should have closed at line 3314, but instead it has a string literal

# Fix:
if '    "  ]\\n"' in lines[3313] or lines[3313] == '    "  ]\\n",':
    print("\nFixing line 3314...")
    lines[3313] = '   ],'  # Actually close the source array

if lines[3314] == '  " },\\n",' or lines[3314] == '  " },\n",':
    print("Fixing line 3315...")
    lines[3314] = '  },'  # Actually close the cell object

# Now lines 3315-3321 should be a new cell (Section 13 header)
# But they're malformed. Let me check:
print("\nAfter fixes:")
print("Line 3314: %s" % repr(lines[3313]))
print("Line 3315: %s" % repr(lines[3314]))

# The Section 13 header content is in lines 3315-3320
# It needs to be a proper cell object starting with {
# Currently line 3315 is: '    " {\\n",' which is a STRING
# Line 3316: '    "  \\"cell_type\\": \\"markdown\\",\\n",' STRING
# etc.

# The Section 13 content needs to be REMOVED and the Section 13 cell
# inserted as a proper cell AFTER the Fig11 cell

# For now, let me just try to fix the immediate JSON structure
# Replace the broken Section 13 content with a placeholder

# Remove lines 3315-3322 (the broken Section 13 content)
# and insert proper Section 13 header cell

# First, let's check what's at line 3321 (index 3320)
print("\nLine 3321: %s" % repr(lines[3320]))
print("Line 3322: %s" % repr(lines[3321]))
print("Line 3323: %s" % repr(lines[3322]))
print("Line 3324: %s" % repr(lines[3323]))

# Save
new_content = '\n'.join(lines)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("\nSaved initial fixes")

# Verify JSON
try:
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("JSON error: %s at line %d" % (e.msg, e.lineno))
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        marker = ">>> " if i+1 == e.lineno else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
