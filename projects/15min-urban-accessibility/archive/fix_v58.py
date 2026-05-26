NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Current structure:
# Line 3314: '   ],\r'  <- source array closes, OK
# Line 3315: '   }\r'   <- cell object closes, OK
# Line 3316: ' ]\r'    <- WRONG! This closes cells array prematurely
# Line 3317: ' "metadata": {\r' <- metadata is now at top level

# Fix: Change ' ]\r' to '  ],\r' and add comma before next cell

# But wait - if this is the LAST cell, there should be a comma after ]
# And the metadata comes AFTER the cells array closes

# Let me understand the structure:
# After the last cell closes, we need:
#   ],\r  <- close cells array (with comma because there might be more at top level)
# But wait, metadata is inside the notebook, not at top level

# Let me look at the structure again
# Current: cells array -> cell -> source array -> cell object
# Then immediately: ] closes cells array
# Then: "metadata" appears

# This means the notebook structure is:
# {
#   "cells": [ ... ],
#   "metadata": { ... }
# }

# So the fix is:
# 1. Add comma after the last cell (line 3315: '   }\r')
# 2. Change line 3316 from ' ]\r' to '  ],\r'

# Actually, the issue is:
# Line 3315: '   }\r' - closes the cell object
# Line 3316: ' ]\r' - closes the cells array
# Then metadata

# But there should be more cells after this! Let me check...

# Actually looking at the lines:
# Line 3316: ' ]\r' closes the cells array
# Then line 3317: ' "metadata": {\r' starts metadata

# This structure is correct IF this is the last cell!
# But the error says "Expecting ',' delimiter" which means JSON expects more content

# Let me check if there are supposed to be more cells after line 3315
# Looking at the original structure from check_structure.py:
# Line 3046: '  {' <- starts a new cell
# Line 3047: '   "cell_type": "markdown",\r' <- markdown cell
# ...
# Line 3068: '   "cell_type": "code",\r' <- starts Section 10 code

# So the structure should be:
# - Cells before Section 10
# - Section 9 markdown cell (lines 3046-3066)
# - Section 10 code cell (lines 3067+)
# - Then more cells

# But currently line 3316 closes the cells array!
# This means all the Section 10+ cells are MISSING!

# Let me check: is line 3046 really at the cell level or inside?
# From check_structure.py:
# Line 3046: '  {\r' - 2 spaces = cell level
# Line 3047: '   "cell_type": "markdown",\r' - 3 spaces = inside cell

# So lines 3046-3066 ARE part of the cells array
# And they should NOT be outside the cells array

# The fix: change line 3316 from ' ]\r' to '  ],\r'
# to keep the cells array open

old = b' ]\r\n "metadata"'
new = b'  ],\r\n "metadata"'

pos = raw.find(old)
print("Pattern ' ]\\r\\n \"metadata\"' at byte: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-30:pos+50]))
    
    new_raw = raw.replace(old, new, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Fixed!")
    
    # Verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS! %d cells" % len(nb['cells']))
        
        for i, cell in enumerate(nb['cells']):
            cell_type = cell.get('cell_type', 'unknown')
            src = cell.get('source', [])
            if isinstance(src, list):
                first_line = src[0].strip()[:60] if src else '(empty)'
            else:
                first_line = str(src)[:60]
            print("  Cell %d: %s | %s" % (i, cell_type, first_line))
            
    except json.JSONDecodeError as e:
        print("Still broken: %s at line %d" % (e.msg, e.lineno))
else:
    print("Pattern not found")
