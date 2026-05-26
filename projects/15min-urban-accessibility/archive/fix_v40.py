NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

# Let me search for the pattern more precisely
# Looking for: b'"\\r\n   ],' (my bad fix)
# This means: quote, backslash, r, backslash, n, comma

search = b'"\\r\\n   ],'
pos = raw.find(search)
print("Found bad fix at byte: %d" % pos)
if pos >= 0:
    print("Context: %s" % repr(raw[pos-20:pos+30]))
    
    # Restore: Change back to '",\r\n   ],'
    new_raw = raw.replace(b'"\\r\\n   ],', b'",\r\n   ],', 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Restored!")
    
    # Now verify
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Error: %s at line %d" % (e.msg, e.lineno))
