NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# ================================================================
# The broken section (after Section 13 header) is:
# "    \"  ]\\n\",\r\n    \" },\r\n ],\r\n
# 
# Should be:
# "    \"  ]\\n\",\r\n    \" },\n\",\r\n  ],\r\n "metadata\": {\r\n...
# ================================================================

# OLD pattern (broken): "    },\r\n ],\r\n
# In hex: 22 20 20 20 20 7D 2C 0D 0A 20 20 5D 2C 0D 0A
OLD_PATTERN = (
    b'"    },\r\n'
    b' ],\r\n'
)

# NEW pattern (fixed):
NEW_PATTERN = (
    b'"    },\n",\r\n'
    b'  ],\r\n'
    b' "metadata": {\r\n'
    b'  "kernelspec": {\r\n'
    b'   "display_name": "Python 3",\r\n'
    b'   "language": "python",\r\n'
    b'   "name": "python3"\r\n'
    b'  },\r\n'
    b'  "language_info": {\r\n'
    b'   "name": "python",\r\n'
    b'   "version": "3.10.0"\r\n'
    b'  }\r\n'
    b' },\r\n'
    b' "nbformat": 4,\r\n'
    b' "nbformat_minor": 4\r\n'
    b'}'
)

# Find the pattern in the file
idx = raw.find(OLD_PATTERN)
print("Broken pattern at byte %d" % idx)

if idx >= 0:
    print("\nFound! Applying fix...")
    print("OLD pattern (hex):", OLD_PATTERN.hex())
    print("OLD pattern (str):", OLD_PATTERN.decode('utf-8', errors='replace'))
    
    # Show context
    ctx = raw[idx-50:idx+len(OLD_PATTERN)+50]
    print("\nContext before fix:")
    print("  hex:", ctx.hex())
    print("  str:", ctx.decode('utf-8', errors='replace'))
    
    # Apply fix
    new_raw = raw[:idx] + NEW_PATTERN + raw[idx+len(OLD_PATTERN):]
    
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
        
        # Save
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
    # Try to find a similar pattern
    # Search for "    }," in the last part of the file
    search = b'"    },'
    idx2 = raw.rfind(search)
    print("'\"    },' found at byte %d" % idx2)
    if idx2 >= 0:
        ctx = raw[idx2:idx2+100]
        print("Context:", repr(ctx.decode('utf-8', errors='replace')))
