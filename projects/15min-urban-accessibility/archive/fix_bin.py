NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d bytes" % len(raw))

# Find the problematic region: "    \"def load_api_config()"
# In bytes: 22 20 20 20 20 5c 22 64 65 66 ...
search = b'    "    \\"def load_api_config()'
idx = raw.find(search)
if idx < 0:
    print("Pattern not found!")
    # Try broader search
    idx = raw.find(b'def load_api_config')
    print("Broad search found at %d: %s" % (idx, raw[idx:idx+40]))
else:
    print("Pattern found at byte %d" % idx)

# Show 100 bytes around it
print("\nContext around position %d:" % idx)
ctx = raw[idx:idx+100]
print("  hex:", ctx.hex())
print("  str:", ctx)

# Count the backslash before 'def' - is it \ or \\ ?
print("\n--- Detailed byte analysis ---")
for i, b in enumerate(raw[idx:idx+20]):
    print("  offset %d (abs %d): 0x%02x = %r" % (i, idx+i, b, bytes([b])))

# The issue: in the file, it might be "  \"def" (broken) instead of "    \"def" (correct)
# Let's find what comes BEFORE "def" in this string
# In correct JSON: "    \"def = quote + 4 spaces + backslash + quote + d + e + f
# In broken JSON:  "  \"def = quote + 2 spaces + backslash + quote + d + e + f
