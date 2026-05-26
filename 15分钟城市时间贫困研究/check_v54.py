NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Check current bytes
pos = 166400
chunk = raw[pos:pos+80]
print("Bytes %d-%d:" % (pos, pos+len(chunk)))
print("Hex: %s" % ' '.join('%02X' % b for b in chunk))
print("Decoded: %s" % chunk.decode('utf-8', errors='replace'))

# Also try json.loads with error position
try:
    json.loads(raw)
except json.JSONDecodeError as e:
    print("\nJSON Error: %s at line %d, col %d" % (e.msg, e.lineno, e.colno))
    
    # Show context
    lines = raw[:e.pos].decode('utf-8', errors='replace').split('\n')
    print("Last 5 lines before error:")
    for i in range(max(0, len(lines)-5), len(lines)):
        print("  Line %d: %s" % (i+1, repr(lines[i][:80])))
