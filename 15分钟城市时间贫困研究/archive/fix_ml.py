NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# CONFIRMED STRUCTURE:
# Line 3314: '    "  ]\n",'     <- closes Section 10's source array  
# Line 3315: '    " },\n",'      <- closes Section 10 cell object
# Line 3316: '  {\n",'          <- opens Section 13 cell
# Lines 3317-3322: Section 13 markdown cell (properly closed)
# Lines 3323-3329: MALFORMED Section 14 code cell (to REMOVE)
# Line 3330: '  { '              <- opens Section 9 cell (keep)
# Lines 3331+: Section 9 markdown cell
#
# ACTION:
# Remove lines 3323-3329 (7 lines)
# Replace line 3323 (which becomes '  {') with '  { \n",' (proper open)
# ================================================================

print("=== BEFORE ===")
print("Line 3314:", repr(lines[3313][:80]))
print("Line 3315:", repr(lines[3314][:80]))
print("Line 3316:", repr(lines[3315][:80]))
print("Line 3317:", repr(lines[3316][:80]))
print("Line 3320:", repr(lines[3319][:80]))
print("Line 3322:", repr(lines[3321][:80]))
print("Line 3323:", repr(lines[3322][:80]))
print("Line 3324:", repr(lines[3323][:80]))
print("Line 3325:", repr(lines[3324][:80]))
print("Line 3326:", repr(lines[3325][:80]))
print("Line 3327:", repr(lines[3326][:80]))
print("Line 3328:", repr(lines[3327][:80]))
print("Line 3329:", repr(lines[3328][:80]))
print("Line 3330:", repr(lines[3329][:80]))
print("Line 3331:", repr(lines[3330][:80]))

# Remove lines 3323-3329 (indices 3322-3328), replace line 3323 with proper open
# After removal, what was line 3330 becomes line 3323
# But line 3330 is '  { ' - we need to replace it with '  { \n",'

# Build new lines: keep 0-3322, then the proper opening, then lines 3331+
# Line 3331 is '  { ' (after removal it becomes line 3323)
# But actually, line 3330 is '  { ' (4 spaces + '{' + space)

# Let me check: line 3330 should be the open of Section 9 cell
# The cell structure should be:
#   " {" -> cell opens
#   "  "cell_type": "markdown"," -> cell_type field
# etc.

# Current line 3330: '  { ' (4 spaces + '{')
# But in JSON it needs to be: '  { \n",' (with newline and comma in JSON string format)

# So I'll replace line 3330 with '  { \n",'

# Remove lines 3323-3329 (indices 3322-3328)
removed = lines[3322:3329]
print("\n=== REMOVING lines 3323-3329 ===")
for i, r in enumerate(removed):
    print("  Removed line %d: %s" % (3323+i, repr(r[:60])))

new_lines = lines[:3322] + lines[3329:]

print("\n=== AFTER REMOVAL ===")
print("New total lines:", len(new_lines))
print("Line 3323:", repr(new_lines[3322][:80]))
print("Line 3324:", repr(new_lines[3323][:80]))
print("Line 3325:", repr(new_lines[3324][:80]))
print("Line 3326:", repr(new_lines[3325][:80]))

# Fix line 3330 (was '  { ') -> '  { \n",'
# After removal, this is now line 3330 (idx 3329)
# But the actual Section 9 cell open is at new_lines[3330-1]
# Let me find the Section 9 cell type line
print("\n=== Finding Section 9 cell type ===")
for i in range(3320, 3340):
    if i < len(new_lines):
        l = new_lines[i].strip()
        if 'cell_type' in l:
            print("Line %d: %s" % (i+1, repr(new_lines[i][:80])))
        if l.startswith('{') or l.startswith('}'):
            print("Line %d: %s" % (i+1, repr(new_lines[i][:80])))

# The Section 9 cell should open at line 3330 (idx 3329)
# Current: '  { '
# Need: '  { \n",'
print("\nLine 3330:", repr(new_lines[3329][:80]))

# Fix
old_open = new_lines[3329]
new_open = '  {\\n",'

if old_open.strip() == '{':
    new_lines[3329] = new_open
    print("Fixed Section 9 cell open")
else:
    print("WARNING: Unexpected content at line 3330:", repr(old_open))

print("\nLine 3330 after fix:", repr(new_lines[3329]))

# Build and save
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
