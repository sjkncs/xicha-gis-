NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# The problematic line 364 has:
# '"    "    print(\"  Run geocode_nominatim.py or geocode_amap.py first\")\n",'
# Should be:
# '"        print(\"  Run geocode_nominatim.py or geocode_amap.py first\")\n",'

# Fix: Change '    "    "' to '        '
old = b'"    "    print(\\"  Run geocode_nominatim.py or geocode_amap.py first\\")\\n",'
new = b'"        print(\\"  Run geocode_nominatim.py or geocode_amap.py first\\")\\n",'

pos = raw.find(old)
print("Pattern at byte: %d" % pos)

if pos >= 0:
    print("Found!")
    new_raw = raw.replace(old, new, 1)
    
    with open(NOTEBOOK_PATH, 'wb') as f:
        f.write(new_raw)
    print("Fixed!")
    
    try:
        with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
            nb = json.load(f)
        print("SUCCESS! %d cells" % len(nb['cells']))
    except json.JSONDecodeError as e:
        print("Error: %s at line %d" % (e.msg, e.lineno))
else:
    print("Pattern not found")
    
    # Search for partial match
    search = b'Run geocode_nominatim.py'
    pos2 = raw.find(search)
    print("'Run geocode_nominatim.py' at: %d" % pos2)
    if pos2 >= 0:
        print("Context: %s" % repr(raw[pos2-30:pos2+60]))
