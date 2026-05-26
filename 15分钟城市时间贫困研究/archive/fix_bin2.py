NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

lines = content.split('\n')
print("Total lines:", len(lines))

# Apply our fix
correct_replacement = (
    '    "    \\"def load_api_config():\\n\\",\\n'
    '    "\\n\\",\\n'
    '    "    config = \\{\\}\\\\n\\",\\n'
)
lines[3347] = correct_replacement
fixed_content = '\n'.join(lines)

# Save first (so we can check the file)
with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    f.write(fixed_content)
print("Saved to file")

# Now open the saved file in binary mode and check the exact bytes
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

# Find the "def load_api_config" region
idx = raw.find(b'def load_api_config')
print("\n'def load_api_config' found at byte %d" % idx)

# Show 200 bytes from there
chunk = raw[idx-30:idx+200]
print("\n200 bytes around the region:")
print(chunk)
print("\nHex:")
print(chunk.hex())

# Now find the EXACT error position
try:
    nb = json.loads(fixed_content)
    print("JSON valid!")
except json.JSONDecodeError as e:
    pos = e.pos
    ln = fixed_content[:pos].count('\n') + 1
    col = pos - fixed_content.rfind('\n', 0, pos) - 1
    print("\nError at byte/char %d, line %d col %d: %s" % (pos, ln, col, e.msg))
    
    # Show exact context
    start = max(0, pos-50)
    end = min(len(fixed_content), pos+100)
    ctx = fixed_content[start:end]
    print("\nContext (repr):")
    print(repr(ctx))
    
    # Show bytes in binary
    ctx_bytes = raw[start:end]
    print("\nContext (hex):")
    for i in range(0, len(ctx_bytes), 40):
        print("  %04d: %s" % (start+i, ctx_bytes[i:i+40].hex()))
    
    # What is at pos?
    print("\nByte at pos %d: 0x%02x = %r" % (pos, raw[pos], bytes([raw[pos]])))
    
    # What comes after?
    print("Next 10 bytes:")
    for i in range(pos, min(pos+10, len(raw))):
        print("  pos %d: 0x%02x = %r" % (i, raw[i], bytes([raw[i]])))
