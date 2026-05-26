NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Show the current broken end
print("\n=== Current end (lines 3318+) ===")
for i in range(3317, min(3340, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:100])))

# ================================================================
# STRATEGY: 
# Keep lines 0-3321 (up to Section 13 cell close '    " },\n",')
# Replace lines 3322-end with proper ending
# ================================================================

# Check: does line 3322 contain the Section 13 close?
print("\nLine 3322:", repr(lines[3321][:80]))
print("Line 3323:", repr(lines[3322][:80]))
print("Line 3324:", repr(lines[3323][:80]))

# Build proper ending
proper_ending = [
    '  ],\\n',       # close cells array
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

# Keep lines 0-3321 (indices 0-3321), replace 3322+ with proper ending
# Note: index 3321 is the LAST valid line (Section 13 cell close)
# We want to keep lines 0 through 3321 (inclusive, 0-indexed)

print("\n=== Rebuilding file ===")
print("Keeping lines 1-3322 (0-3321)")
print("Replacing lines 3323+ with proper ending")

# Take first 3322 lines (indices 0-3321)
new_lines = lines[:3322]

# Add proper ending
for l in proper_ending:
    new_lines.append(l)

print("New total lines: %d" % len(new_lines))
print("Last line:", repr(new_lines[-1]))

# Build and validate
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
