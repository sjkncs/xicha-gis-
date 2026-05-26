NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# ================================================================
# Line 3322 is broken: '    " },' 
# Should be: '    "  ]\\n",' (close source array with newline)
# ================================================================

print("BEFORE line 3322:", repr(lines[3321]))
print("BEFORE line 3323:", repr(lines[3322]))

# Fix line 3322
OLD = '    " },'
NEW = '    "  ],\\n",'

if OLD in lines[3322]:
    lines[3322] = NEW
    print("Fixed line 3322")
else:
    print("Pattern not found! Line 3322:", repr(lines[3321]))

print("AFTER line 3322:", repr(lines[3321]))

# ================================================================
# Now remove lines 3323-3329 (broken Section 13 code cell remnants)
# ================================================================
# Lines 3323-3329 (indices 3322-3328) are the broken cell:
# Line 3323: '    "  ],\\n",'
# Line 3324: '    " },\\n",'
# Line 3325: '    " {\\n",'
# Line 3326: '' (empty)
# Line 3327: '    "<a id=\\'9\\'></a>...' <- Section 9 content
# Line 3328: '   ]'
# Line 3329: '  }'

print("\n=== Removing broken cell lines 3323-3329 ===")
for i in range(3322, 3329):
    print("  Removing line %d: %s" % (i+1, repr(lines[i][:60])))

# Remove lines 3323-3329, keep 3330+
# After removing, the Section 9 content (was line 3327) moves to line 3323
removed = lines[3322:3329]
lines = lines[:3322] + lines[3329:]

print("\n=== After removal ===")
print("New total lines:", len(lines))
print("Line 3323:", repr(lines[3322][:80]))
print("Line 3324:", repr(lines[3323][:80]))
print("Line 3325:", repr(lines[3324][:80]))

# But wait - Section 9 content (line 3327, now line 3323 after removal)
# has this format: '    "<a id=\\'9\\'></a>...' (no comma at end!)
# We need to add closing brackets for the Section 9 cell

# Section 9 content starts at line 3323 (after removal)
# The cell structure should be:
# Line N: '    " {\\n",'        <- open cell
# Line N+1: '   "cell_type": "markdown",\\n",' <- cell_type field
# Line N+2: '   "metadata": {},\\n",' <- metadata field
# Line N+3: '   "source": [\\n",' <- source array open
# Line N+4: content <- the actual content
# After content: '   ],\\n",' <- close source array
#              '  },\\n",' <- close cell
#              '  {\\n",' <- open next cell

# Currently line 3323 = Section 9 content (no trailing comma)
# We need to add: '   ],\\n",' then '  },\\n",' then '  {\\n",' (Section 14 if needed, or just let Section 9 end)

# But wait - looking at line 3325 onwards:
# Line 3325: '   ]'  <- close source array
# Line 3326: '  }'   <- close cell
# Line 3327: ' ],'    <- close cells array
# These are the closing brackets for the Section 9 cell!

# So after line 3323 (Section 9 content), we need:
# '   ],\\n",'  <- close source array
# '  },\\n",'  <- close cell
# '  {\\n",'    <- open Section 14 (or remove if none)
# But lines 3325-3327 already have ']', '}', ']'...

# The issue is the Section 9 content doesn't have a comma at the end!
# Fix: Add trailing comma to Section 9 content

content_line = lines[3322]  # Section 9 content
print("\n=== Section 9 content ===")
print("Line 3323:", repr(content_line[:100]))
print("Does it end with \",? ", content_line.rstrip().endswith('",'))

# Check lines 3324-3328
print("\nLines 3324-3328:")
for i in range(3323, 3328):
    print("  Line %d: %s" % (i+1, repr(lines[i][:60])))

# The Section 9 content line (3323) ends without a comma
# We need to add a comma and closing brackets
# Replace line 3323 with content + ','
lines[3322] = content_line.rstrip('\n') + ',\\n'

print("\n=== After adding comma ===")
print("Line 3323:", repr(lines[3322][:100]))

# Now lines 3324-3326 should be: '   ]\\n",'  '  },\\n",'  '  {\\n",'
# But currently they're:
# Line 3324: '   ]'  (no comma, no \n")
# Line 3325: '  }'   (no comma, no \n")
# Line 3326: ' ],'   (close cells array)

print("\n=== Checking closing brackets ===")
print("Line 3324:", repr(lines[3323]))
print("Line 3325:", repr(lines[3324]))
print("Line 3326:", repr(lines[3325]))

# Fix lines 3324 and 3325
# Line 3324: '   ]' -> '   ],\\n",'
# Line 3325: '  }' -> '  },\\n",'
# Line 3326: ' ],'  <- this closes the cells array, OK

lines[3323] = '   ],\\n",'
lines[3324] = '  },\\n",'
# Line 3325 stays as ' ],'

print("\n=== After fixing closing brackets ===")
print("Line 3324:", repr(lines[3323]))
print("Line 3325:", repr(lines[3324]))
print("Line 3326:", repr(lines[3325]))

# Also check: is there a '  {\\n",' before Section 9?
# Looking at lines 3320-3322 before the content:
print("\n=== Lines 3318-3322 ===")
for i in range(3317, 3323):
    print("Line %d: %s" % (i+1, repr(lines[i][:80])))

# Now build and validate
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
    print("\nSaved successfully!")
except json.JSONDecodeError as e:
    pos = e.pos
    ln = fixed_content[:pos].count('\n') + 1
    print("Error at line %d: %s" % (ln, e))
    print("Line %d: %s" % (ln, repr(fixed_content.split('\n')[ln-1][:100])))
    ctx = fixed_content[max(0, e.pos-100):e.pos+100]
    print("Context:", repr(ctx))
