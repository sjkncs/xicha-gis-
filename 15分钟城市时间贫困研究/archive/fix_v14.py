NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# From earlier output:
# '},\r\n     ],' found at byte 166664

# Let's look at exactly what's at 166658 (4-space quote pattern)
print("=== Bytes from 166658 ===")
area = raw[166658:166720]
print("Raw bytes:")
print(' '.join('%02X' % b for b in area))

# Now let's find '},\r\n     ],' pattern
BROKEN = b'},\r\n     ],'
pos = raw.find(BROKEN)
print("\nPattern '},\\r\\n     ],' at: %d" % pos)

if pos >= 0:
    print("Found! Context: %s" % repr(raw[pos-10:pos+50]))
    
    # Now let's replace just the '    },' part
    # In hex: 20 20 20 20 22 20 20 7D 2C = "    "  },
    # Should be: 20 20 22 20 20 7D 2C = "  "  },
    
    # But wait, let's check what 5-space ] is
    # 20 20 20 20 20 5D 2C = 5-space ],
    # Should be: 20 20 5D 2C = 2-space ]
    
    # Actually, looking at the decoded output from earlier:
    # '    " },\r\n     ],'
    # That's: 4-space " 2-space },\r\n 5-space ],
    
    # The fix should be: 2-space " 2-space },\r\n 2-space ]
    # = '  },\r\n],'
    
    print("\nApplying fix...")
    new_raw = raw.replace(b'    " },\r\n     ],', b'  },\r\n],', 1)
    
    if new_raw != raw:
        with open(NOTEBOOK_PATH, 'wb') as f:
            f.write(new_raw)
        print("Saved!")
        
        # Verify
        import json
        try:
            with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
                nb = json.load(f)
            print("SUCCESS! %d cells" % len(nb['cells']))
        except json.JSONDecodeError as e:
            print("Still broken: %s at line %d" % (e.msg, e.lineno))
    else:
        print("No change made - pattern not found")
