NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find the Section 13 header
search = b'\\"<a id=\'13\''
idx = raw.find(search)
print("Section 13 header at byte %d" % idx)

# Show 200 bytes from there
chunk = raw[idx:idx+300]
print("\n=== Context ===")
print(repr(chunk.decode('utf-8', errors='replace')))

# Find all CR bytes
cr_positions = []
pos = 0
while True:
    pos = raw.find(b'\r', pos)
    if pos < 0:
        break
    cr_positions.append(pos)
    pos += 1

print("\n=== CR positions (last 20) ===")
for p in cr_positions[-20:]:
    ctx = raw[max(0, p-20):p+30]
    print("  CR at byte %d: %s" % (p, repr(ctx.decode('utf-8', errors='replace'))))

# Find the broken pattern: after Section 13 header, there's a broken structure
# The Section 13 cell is missing its closing - we need to insert:
# "  ]\n",\r\n   }\n",\r\n   },\r\n ],\r\n
# But currently there's just " ],\r\n" directly after the header

# Search for the pattern: "    "  ]\n",\r\n    " },\r\n ],\r\n
# The broken section is the lack of "  ]\n", between the header and the cell close

# Find "    }," in the context of Section 13
broken = b'"    },\r\n ],'
pos_b = raw.rfind(b'"    },\r\n ],')
print("\nBroken pattern at byte %d" % pos_b)

if pos_b >= 0:
    ctx = raw[pos_b-50:pos_b+100]
    print("Context:", repr(ctx.decode('utf-8', errors='replace')))
    
    # Show byte analysis
    print("\nByte analysis of broken section:")
    for i in range(pos_b-20, min(pos_b+50, len(raw))):
        b = raw[i]
        c = chr(b) if 32 <= b < 127 else '.'
        print("  %d: 0x%02x = %r (%s)" % (i, b, bytes([b]), c))
    
    # The fix: Replace "    " },\r\n ], with proper cell close
    # Old: '"    },\r\n ],\r\n'
    # New: '"  },\r\n ],\r\n' (just fix the indentation of the cell close brace)
    # Actually no - the issue is the cell itself is not properly closed
    
    # Looking at the structure:
    # "  "source": [ <- open source array
    #  "<a id='13'>...\\"\\n", <- header content
    #  "  ]\n", <- close source array
    #  "    " },\r\n <- THIS IS WRONG: " 4 spaces" } , but cell is missing!
    #  ], <- close cells array
    
    # What SHOULD be there:
    #  "  ]\n", <- close source array
    #  " },\n", <- close cell object (2 spaces + } + ,)
    #  ], <- close cells array
    
    # The fix is to replace:
    # '"    },\r\n ],\r\n' with '" },\r\n ],\r\n'
    # That is: remove the extra '    "' before '}'
    
    OLD = b'"    },\r\n ],\r\n'
    NEW = b'" },\r\n ],\r\n'
    
    idx_fix = raw.rfind(OLD)
    print("\nFix pattern at byte %d" % idx_fix)
    
    if idx_fix >= 0:
        ctx_fix = raw[idx_fix-30:idx_fix+len(OLD)+30]
        print("Before:", repr(ctx_fix.decode('utf-8', errors='replace')))
        
        new_raw = raw[:idx_fix] + NEW + raw[idx_fix+len(OLD):]
        
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
            print("\nSaved!")
        except json.JSONDecodeError as e:
            print("JSON error: %s" % e)
            text = new_raw.decode('utf-8', errors='replace')
            ln = text[:e.pos].count('\n') + 1
            print("Line %d: %s" % (ln, repr(text.split('\n')[ln-1][:100])))
    else:
        print("Fix pattern not found!")
        # Try to find just '"    },' in the context
        search_broken = b'"    },'
        idx_b = raw.rfind(search_broken)
        print("'\"    },' at byte %d" % idx_b)
        if idx_b >= 0:
            ctx_b = raw[idx_b:idx_b+50]
            print("Context:", repr(ctx_b.decode('utf-8', errors='replace')))
