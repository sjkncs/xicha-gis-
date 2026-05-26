NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find Section 13 header
search = b'\\"<a id=\'13\''
idx = raw.find(search)
print("Section 13 header at byte %d" % idx)

if idx >= 0:
    # Show 1000 bytes from there
    chunk = raw[idx:idx+1000]
    print("\n=== Context from Section 13 header ===")
    print(repr(chunk.decode('utf-8', errors='replace')))
    
    # Now find the metadata structure
    search2 = b'"metadata":'
    idx2 = raw.rfind(search2)
    print("\nLast metadata at byte %d" % idx2)
    if idx2 >= 0:
        chunk2 = raw[idx2:idx2+500]
        print(repr(chunk2.decode('utf-8', errors='replace')))

# Also check the total cells count from the notebook
print("\n=== File structure ===")
print("Total file size: %d bytes" % len(raw))
print("Total newlines: %d" % raw.count(b'\n'))
print("First 100 bytes:")
print(repr(raw[:100]))

# Try to parse JSON
print("\n=== Attempting JSON parse ===")
try:
    text = raw.decode('utf-8')
    nb = json.loads(text)
    print("SUCCESS! %d cells" % len(nb['cells']))
except json.JSONDecodeError as e:
    print("Error at char %d: %s" % (e.pos, e.msg))
    text = raw.decode('utf-8', errors='replace')
    ln = text[:e.pos].count('\n') + 1
    print("Line %d: %s" % (ln, repr(text.split('\n')[ln-1][:100])))
