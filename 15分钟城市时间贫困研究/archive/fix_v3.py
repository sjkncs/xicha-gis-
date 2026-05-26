NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# Line 3322 (1-indexed) = index 3321 = '    " },' (broken)
# Line 3323 (1-indexed) = index 3322 = ' ],'
# 
# STRATEGY: Keep lines 0-3320 (indices 0-3320, i.e. lines 1-3321),
# Fix line 3321 ('    " },' -> '    " },\n",'),
# then add proper cells array close + metadata + ending
# ================================================================

# Check what we have
print("Line 3321:", repr(lines[3320][:80]))  # should be Section 13 source close
print("Line 3322:", repr(lines[3321][:80]))  # should be broken '    " },' 
print("Line 3323:", repr(lines[3322][:80]))  # should be ' ],'

# The correct structure for Section 13 cell close:
# Line: '    "  ]\n",'  <- source array close (line 3321, index 3320, ALREADY CORRECT)
# Line: '    " },\n",' <- cell object close (line 3322, index 3321, BROKEN)
# Line: '  ],\n'   <- cells array close
# Then metadata

# FIX: Replace line 3322 (broken) with proper close
if '    " },' == lines[3321].strip():
    print("\nFixing line 3322...")
    # Replace the entire line 3322
    # Currently: '    " },' (broken, missing \n and trailing comma)
    # Should be: '    " },\n",' (proper close)
    lines[3321] = '    " },\\n",'
    print("Fixed:", repr(lines[3321]))
else:
    print("WARNING: Line 3322 is not what we expected:", repr(lines[3321][:80]))

# Now truncate after line 3322 and add proper ending
# Keep lines 0-3322 (indices 0-3322, lines 1-3323 in 1-indexed)
# Remove lines 3323 onwards
new_lines = lines[:3323]

print("\nAfter truncation:", len(new_lines), "lines")
print("Last line:", repr(new_lines[-1][:80]))

# Add proper ending
proper_ending = [
    '  ],\n',
    ' "metadata": {\n',
    '  "kernelspec": {\n',
    '   "display_name": "Python 3",\n',
    '   "language": "python",\n',
    '   "name": "python3"\n',
    '  },\n',
    '  "language_info": {\n',
    '   "name": "python",\n',
    '   "version": "3.10.0"\n',
    '  }\n',
    ' },\n',
    ' "nbformat": 4,\n',
    ' "nbformat_minor": 4\n',
    '}',
]

for l in proper_ending:
    new_lines.append(l)

print("Final line count:", len(new_lines))

fixed_content = '\n'.join(new_lines)
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
