NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find the escaped Section 13 header
search1 = b'\\"<a id='
idx1 = raw.find(search1)
print("Section 13 header at byte %d" % idx1)

if idx1 >= 0:
    # Show 500 bytes from there
    ctx = raw[idx1:idx1+500]
    print("\n=== Context from Section 13 header ===")
    print("hex:", ctx.hex())
    print("\nstr (repr):", repr(ctx.decode('utf-8', errors='replace')))
    
    # Now find the "    }," pattern in this region
    # It should be somewhere after the header
    for i, b in enumerate(ctx):
        if b == ord('}'):
            pos = idx1 + i
            snippet = raw[pos-5:pos+20]
            if snippet.decode('utf-8', errors='replace').startswith('    }'):
                print("\nFound } at byte %d:" % pos)
                print("  Context: %s" % repr(snippet))
                print("  Hex: %s" % snippet.hex())
