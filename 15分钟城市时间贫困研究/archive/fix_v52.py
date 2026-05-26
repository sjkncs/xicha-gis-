NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The structure around byte 166416:
# b'"print(\'=\'*60)\\n"\\r,\n   ],'
# = quote, print('='*60), backslash-n, quote, backslash-r, comma, LF, spaces, ], comma

# In this structure:
# The string value is: "print('='*60)\n"\r
# After the string, there's a comma (valid for non-last element)
# Then there's ], which is wrong - ] closes the array, but there's more content?

# Wait, let me decode this properly:
# "print('='*60)\n"\r,\n   ],
# = JSON string "print('='*60)\n" + escaped \r + , (comma) + newline + spaces + ]

# But this is WRONG because the last element of an array doesn't need a comma!
# And more importantly, where is the closing quote of the string?

# Let me look at it character by character:
# " = quote (opens string)
# p = 70
# r = 72
# i = 69
# n = 6E
# t = 74
# ( = 28
# ' = 27
# = = 3D
# ' = 27
# * = 2A
# 6 = 36
# 0 = 30
# ) = 29
# \ = 5C
# n = 6E
# " = 22 (closes string)
# \ = 5C
# r = 72
# , = 2C (comma)
# \n = 0A (LF)
# spaces
# ] = 5D (closes array)

# So the structure is:
# "string content\n"\r, (comma!)
# Then ] closes the array

# The issue: There's a comma AFTER the \r, which is correct for a non-last element
# But then ] closes the array immediately after

# The question: is this string the LAST element in the source array?
# If yes, no comma needed
# If no, comma is needed

# Looking at the content before this:
# Line 3312: "print('Fig11 建筑AOI分析完成')\n",
# Line 3313: "print('='*60)\n"\r,
# Then ]

# So line 3313 is the LAST element, and should NOT have a comma!
# Current: \r,\n   ]
# Should be: \r\n   ]

# Fix: Remove the comma after \r

old = b'"\\r,\\n   ],'
new = b'"\\r\\n   ],'

pos = raw.find(old)
print("Looking for: %s" % repr(old))
print("Found at: %d" % pos)

if pos >= 0:
    print("Context: %s" % repr(raw[pos-30:pos+50]))
    
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
    
    # Try different escaping
    # The bytes are: 22 5C 72 2C 0A 20 20 20 5D 2C
    # = " \ r , LF spaces ] ,
    search2 = bytes([0x22, 0x5C, 0x72, 0x2C, 0x0A, 0x20, 0x20, 0x20, 0x5D, 0x2C])
    pos2 = raw.find(search2)
    print("Searching for bytes %s: %d" % (' '.join('%02X' % b for b in search2), pos2))
