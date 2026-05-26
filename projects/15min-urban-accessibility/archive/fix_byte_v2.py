NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Check line ending type
crlf_count = raw.count(b'\r\n')
lf_count = raw.count(b'\n') - crlf_count
print("CRLF (\\r\\n): %d" % crlf_count)
print("LF only (\\n): %d" % lf_count)

# Find the broken section by searching backwards from the end
# Look for the Section 13 header
search = b'\\"<a id=\'13\''
idx = raw.rfind(search)
print("Section 13 header at byte %d" % idx)

if idx >= 0:
    # Show 300 bytes from there
    ctx = raw[idx:idx+300]
    print("\nContext:")
    print(repr(ctx.decode('utf-8', errors='replace')))
    
    # Find the exact bytes
    print("\n=== Byte analysis ===")
    for i, b in enumerate(ctx[:150]):
        c = chr(b) if 32 <= b < 127 else '.'
        print("  offset %d (abs %d): 0x%02x = %r (%s)" % (i, idx+i, b, bytes([b]), c))
