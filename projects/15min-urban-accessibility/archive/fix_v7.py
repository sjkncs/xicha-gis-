NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# From the hex dump, the Section 13 cell closes with:
# 20 20 20 20 22 20 7D 2C 0D 0A 20 5D 2C 0D 0A 20 22 6D 65 74
# = "    " },\r\n ],\r\n "metadata
# Should be:
# 20 20 22 20 7D 2C 0D 0A 5D 2C 0D 0A 20 22 6D 65 74
# = "  },\r\n],\r\n "metadata

# The fix: replace '    " },\r\n ],\r\n' with '  },\r\n],\r\n# i.e. remove 2 spaces from '    " },' to get '  },'
# and remove 2 spaces from '     ],' to get '],'

# First, let's find the exact pattern
idx = raw.find(b"id='13'")
meta_idx = raw.find(b'"metadata":')
print("id='13' at: %d" % idx)
print("'metadata' at: %d" % meta_idx)

# The area between them is the Section 13 header cell
# Let's look at the last 50 bytes before metadata
pre_meta = raw[meta_idx-50:meta_idx]
print("\n50 bytes before 'metadata':")
print(' '.join('%02X' % b for b in pre_meta))
print(repr(pre_meta.decode('utf-8', errors='replace')))

# Now find the specific bytes to replace
# Pattern: 20 20 20 20 22 20 7D 2C = "    " }, 
# But in the file it's: 22 20 20 20 20 7D 2C = "     },

# Actually from the hex: 20 20 20 20 22 20 7D 2C 0D 0A 20 5D 2C
# That's:     " },\r\n ],

# The fix should change:
# BEFORE: 22 20 20 20 20 7D 2C 0D 0A 20 20 20 20 5D 2C  (4-space " }, then 4-space ])
# AFTER:  22 20 20 7D 2C 0D 0A 5D 2C (2-space " }, then 0-space ])

BROKEN = b'"    },\r\n     ],'
FIXED = b'"  },\r\n],'

pos = raw.find(BROKEN)
print("\nPattern '\"    },\\r\\n     ],' at byte: %d" % pos)

if pos >= 0:
    print("Found! Fixing...")
    print("Context: %s" % repr(raw[pos-10:pos+50]))
    new_raw = raw.replace(BROKEN, FIXED, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Saved!")
    
    # Verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Still broken: %s at line %d" % (e.msg, e.lineno))
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
            marker = ">>> " if i+1 == e.lineno else "    "
            print("%s%d: %s" % (marker, i+1, repr(lines[i])))
else:
    print("Pattern not found. Let me search for alternatives...")
    
    # Try different patterns
    patterns = [
        b'"    },\r\n     ],',
        b'"    },\r\n    ],',
        b'"    },],\r\n',
        b'"    },\n     ],',
        b'"    },  ],',
        b'"  },  ],',
    ]
    
    for p in patterns:
        count = raw.count(p)
        if count > 0:
            print("  '%s' found %d times" % (repr(p), count))
