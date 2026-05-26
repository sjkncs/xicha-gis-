NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# CURRENT STATE:
# Line 3320: Section 13 header source (the only remaining Section 13 element)
# Line 3321: close source '    "  ]\n",'
# Line 3322: '    " },' (BROKEN: missing closing comma in string)
# Line 3323: ' ],' (BROKEN: closes cells array prematurely)  
# Lines 3324-3333: metadata fields (language_info etc.)
#
# MISSING:
# 1. Section 9 markdown cell (completely gone)
# 2. Proper closing of Section 13 cell
# 3. Proper closing of cells array
# 4. Section 9 content (the full markdown text)
#
# TARGET STATE:
# Lines up to 3321 (keep as-is)
# Line 3322: '    " },\n",' (fix close of Section 13 cell)
# Line 3323: '  ],\n' (close cells array)
# Lines 3324-3334: metadata (keep as-is)
# ================================================================

print("=== Current lines 3318-3340 ===")
for i in range(3317, min(3340, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# ================================================================
# FIX 1: Line 3322 - '    " },' should be '    " },\n",'
# ================================================================
OLD_3322 = '    " },'
NEW_3322 = '    " },\\n",'
if OLD_3322 in lines[3321]:
    print("\nFIX 1: Fixing line 3322")
    lines[3321] = NEW_3322
    print("  Before:", repr('    " },'))
    print("  After:", repr(NEW_3322))
else:
    print("FIX 1: Pattern not found at line 3322:", repr(lines[3321]))

# ================================================================
# FIX 2: Lines 3323-3333 - Remove the malformed metadata that started
# inside the Section 14 code cell's source array
# These lines: ' ],', ' "metadata": {'... '  "language_info"... ' },' ' "nbformat"...
# They're the metadata of the Section 9 cell that got corrupted
# ================================================================
print("\nFIX 2: Removing lines 3323-3333 (malformed metadata stub)")
for i in range(3322, 3334):
    if i < len(lines):
        print("  Removing line %d: %s" % (i+1, repr(lines[i][:60])))
        lines[i] = None  # Mark for removal

# Remove None entries
lines = [l for l in lines if l is not None]
print("After removal: %d lines" % len(lines))

# ================================================================
# FIX 3: Insert proper closing brackets for cells array
# ================================================================
# After removal, what's at line 3322?
print("\nFIX 3: Checking line 3322 after removal")
print("Line 3322:", repr(lines[3321][:80]))

# The cells array needs to be closed with '  ],\n'
# Then metadata starts with ' "metadata": {\n'
# Let me find where to insert the close

# Lines 3321 is now the last line of Section 13 cell ('    " },\n",')
# We need to:
# 1. Close the cells array: '  ],\n'
# 2. Start metadata: ' "metadata": {\n'
# But also need Section 9 cell!

# Wait - I need to add Section 9 cell too!
# Section 9 markdown cell:
#   {
#    "cell_type": "markdown",
#    "metadata": {},
#    "source": [
#     "<a id='9'>...</a>...",
#    ]
#   },

# Let me find where Section 13 ends
print("\n=== Lines around 3318-3325 ===")
for i in range(3317, 3326):
    if i < len(lines):
        print("Line %d: %s" % (i+1, repr(lines[i][:80])))

# The Section 13 cell closes at line 3321 (now '    " },\n",')
# After it, we need:
# 1. '  ],\n' - close cells array
# 2. ' "metadata": {\n' - open metadata
# 3. '  "kernelspec": {\n' - kernelspec
# 4. '   "display_name": "Python 3",\n' etc. (from original metadata)
# 5. '  },\n' - close metadata
# 6. ' "nbformat": 4,\n' etc.

# So we replace lines 3322 onwards with the proper metadata

# But first, what are the original metadata lines?
# From earlier analysis (before corruption):
# Line 3331: ' "metadata": {'
# Line 3332: '  "kernelspec": {'
# Line 3333: '   "display_name": "Python 3",'
# Line 3334: '   "language": "python",'
# Line 3335: '   "name": "python3"'
# Line 3336: '  },'

# Let me find the closing bracket position
for i, l in enumerate(lines):
    if l.strip() == '}' and i > 3300:
        print("Found } at line %d: %s" % (i+1, repr(l)))

# Find where metadata starts
for i, l in enumerate(lines):
    if 'language_info' in l or 'kernelspec' in l or 'metadata' in l:
        print("Line %d: %s" % (i+1, repr(l[:80])))

# Let me rebuild the end of the file properly
# Lines after Section 13 cell close should be:
# '  ],\n' (close cells array)
# ' "metadata": {\n' (open metadata)
# ... (kernelspec, language_info) ...
# ' },\n' (close metadata)
# ' "nbformat": 4,\n'
# ' "nbformat_minor": 4\n'
# '}'

# The key question: what is the very last valid line of Section 13 cell?
# After fix 1, line 3321 is '    " },\n",'

# So we need to:
# 1. Keep lines 0-3321 (up to and including Section 13 cell close)
# 2. Add '  ],\n' (close cells array) 
# 3. Add proper metadata
# 4. Close the file

# Check if there are any more content lines after 3321
print("\n=== Lines 3322 to end ===")
for i in range(3321, min(len(lines), 3340)):
    print("Line %d: %s" % (i+1, repr(lines[i][:80])))

# There are metadata-like lines from 3323 onwards
# Let me try a different approach: fix lines 3323+ to be valid metadata

# Remove lines 3323 onwards
lines = lines[:3323]  # Keep up to line 3322 (Section 13 cell close)

print("\nAfter truncation: %d lines" % len(lines))
print("Last line %d: %s" % (len(lines), repr(lines[-1][:80])))

# Add proper closing
proper_ending = [
    '  ],\\n',
    ' "metadata": {\\n',
    '  "kernelspec": {\\n',
    '   "display_name": "Python 3",\\n',
    '   "language": "python",\\n',
    '   "name": "python3"\\n',
    '  },\\n',
    '  "language_info": {\\n',
    '   "name": "python",\\n',
    '   "version": "3.10.0"\\n',
    '  }\\n',
    ' },\\n',
    ' "nbformat": 4,\\n',
    ' "nbformat_minor": 4\\n',
    '}',
]

print("\n=== Adding proper ending ===")
for l in proper_ending:
    lines.append(l)
    print("  Added:", repr(l))

print("\nFinal line count: %d" % len(lines))

# Build and validate
fixed_content = '\n'.join(lines)

# Add trailing newline
fixed_content += '\n'

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
    print("\nSaved successfully!")
except json.JSONDecodeError as e:
    pos = e.pos
    ln = fixed_content[:pos].count('\n') + 1
    print("Error at line %d: %s" % (ln, e))
    print("Line %d: %s" % (ln, repr(fixed_content.split('\n')[ln-1][:100])))
    ctx = fixed_content[max(0, e.pos-100):e.pos+100]
    print("Context:", repr(ctx))
