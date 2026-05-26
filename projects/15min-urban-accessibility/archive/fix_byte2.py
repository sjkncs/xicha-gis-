NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Search for the escaped Section 13 header
# In JSON file: \"<a id='13'
search1 = b'\\"<a id='
idx1 = raw.find(search1)
print("Escaped Section 13 header at byte %d" % idx1)

if idx1 < 0:
    print("NOT FOUND - searching for Section 9 instead...")
    search2 = b'\\"<a id='
    idx2 = raw.find(search2)
    print("Escaped id= found at byte %d" % idx2)
    if idx2 >= 0:
        print("Context:", raw[idx2:idx2+50])

# Search for the broken "    }," pattern
# In JSON file: "    },"  (with escape)
search3 = b'"    },'  
idx3 = raw.find(search3)
print("\n'\"    },' pattern at byte %d" % idx3)

if idx3 >= 0:
    # Show context
    ctx = raw[idx3:idx3+100]
    print("\nContext around broken pattern:")
    print("  hex:", ctx.hex())
    print("  str:", ctx.decode('utf-8', errors='replace'))
    
    # Show char by char
    print("\nByte analysis:")
    for i in range(idx3, min(idx3+30, len(raw))):
        b = raw[i]
        c = chr(b) if 32 <= b < 127 else '.'
        print("  pos %d: 0x%02x = %r" % (i, b, bytes([b])))
