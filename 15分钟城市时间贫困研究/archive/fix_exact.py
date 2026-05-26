NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# ================================================================
# The broken section in the file:
# Offset 78-86: '    ' (4 spaces) 
# Offset 87-93: '"  ]\n",' (close Section 13 source array)
# Offset 94-95: '\r\n'
# Offset 96-99: '    ' (4 spaces)
# Offset 100-105: '" },\r\n' <- WRONG: This should be inside the string literal
# Offset 106-109: '    ]' <- WRONG: This closes the cells array but cell isn't closed
# 
# In bytes:
# 166660-166665: 20 20 20 20  (4 spaces) 
# 166666-166671: 22 20 20 20 20 7D 2C  (5 spaces + " } ,)
# 166672-166673: 0D 0A  (\r\n)
# 166674-166677: 20 20 20 20  (4 spaces)
# 166678-166680: 5D 2C 0D 0A  (] ,\r\n)
#
# THE FIX: The cell object " { " at the beginning of Section 13 cell is missing " }," close
# We need to insert "  },\r\n" (the closing of the Section 13 cell object)
# between byte 166673 (after \r\n) and byte 166674 (4 spaces)
#
# OLD bytes: 0D 0A 20 20 20 20 5D 2C 0D 0A
# NEW bytes: 0D 0A 20 20 20 20 7D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A
#            ^end line  |4 spaces  ] , CRLF    -> ^4 spaces  } , CRLF |4 spaces  ] , CRLF
# ================================================================

# Find the exact pattern: after Section 13 header close, the pattern is:
# '\r\n    "  ]\n",\r\n    " },\r\n ],\r\n "metadata": {'
# We need to insert '  },\r\n' (cell close) after the "},\r\n" part

# In hex, the broken pattern is:
# 0D 0A 20 20 20 20 5D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A 20 20
# We want:
# 0D 0A 20 20 20 20 7D 2C 0D 0A 20 20 20 20 5D 2C 0D 0A 20 20

# Let me find the exact location
OLD_SEQ = b'\r\n    " },\r\n ],\r\n'
idx = raw.find(OLD_SEQ)
print("Broken pattern at byte %d" % idx)

if idx >= 0:
    ctx = raw[idx-30:idx+len(OLD_SEQ)+30]
    print("\nContext:")
    print("  hex:", ctx.hex())
    print("  str:", ctx.decode('utf-8', errors='replace'))
    
    # Verify the context is right (should be after Section 13 source close)
    before = raw[idx-30:idx]
    print("\n  Before:", before.decode('utf-8', errors='replace'))
    
    # The fix: insert "  },\r\n" after "},\r\n"
    # This means replacing:
    # OLD: '\r\n    " },\r\n ],\r\n'
    # NEW: '\r\n    "  },\r\n    " },\r\n ],\r\n'
    # Wait, that's not right either...
    
    # Let me re-analyze. The Section 13 cell structure is:
    # " {      <- cell open (4 spaces + {)
    #  "cell_type": "markdown", <- cell_type field
    #  "metadata": {}, <- metadata field  
    #  "source": [ <- source array open
    #   "<a id='13'>...", <- content
    #  ] <- close source array (already exists as "  ]\n",)
    # } <- close cell object (MISSING!)
    # ,
    #
    # After Section 13 source close: '\r\n    "  ]\n",\r\n    " },\r\n ],\r\n "metadata"...
    #
    # The "    " },\r\n" is trying to close the cell object
    # But it has WRONG indentation (4 spaces) - should be 2 spaces for cell object close
    # And then "    ]," closes the cells array
    #
    # CORRECT:
    # '\r\n    "  ],\r\n' <- close source array
    # '  },\r\n' <- close cell object (2 spaces + } + ,)
    # ' ],\r\n' <- close cells array
    #
    # So the fix is: replace '    " },\r\n ],\r\n' with '  },\r\n ],\r\n'
    
    OLD_FIX = b'\r\n    " },\r\n ],\r\n'
    NEW_FIX = b'\r\n  },\r\n ],\r\n'
    
    idx_fix = raw.find(OLD_FIX)
    print("\nFix pattern at byte %d" % idx_fix)
    
    if idx_fix >= 0:
        print("Found fix pattern!")
        # Verify context
        ctx_fix = raw[idx_fix-50:idx_fix+len(NEW_FIX)+50]
        print("Context:")
        print("  hex:", ctx_fix.hex())
        print("  str:", ctx_fix.decode('utf-8', errors='replace'))
        
        # Apply fix
        new_raw = raw[:idx_fix] + NEW_FIX + raw[idx_fix+len(OLD_FIX):]
        
        print("\n=== Validating JSON ===")
        try:
            text = new_raw.decode('utf-8')
            nb = json.loads(text)
            print("SUCCESS! %d cells" % len(nb['cells']))
            for i, cell in enumerate(nb['cells']):
                ct = cell['cell_type']
                src = ''.join(cell['source'][:1])
                preview = src[:60].replace('\n', '\\n')
                print("  Cell %d: %s -> %s" % (i, ct, preview))
            
            with open(NOTEBOOK_PATH, 'wb') as f:
                f.write(new_raw)
            print("\nSaved successfully!")
        except json.JSONDecodeError as e:
            print("JSON error at char %d: %s" % (e.pos, e))
            text = new_raw.decode('utf-8', errors='replace')
            ln = text[:e.pos].count('\n') + 1
            print("Line %d: %s" % (ln, repr(text.split('\n')[ln-1][:100])))
else:
    print("Pattern not found!")
