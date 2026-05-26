NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

print("File size: %d" % len(raw))

# Find literal CR (0D) not followed by LF (0A) - that's an invalid JSON control character
# OR find bare CR inside JSON string content
positions = []
for i in range(len(raw) - 1):
    if raw[i] == 0x0D:  # CR
        # Check if it's part of CRLF or bare CR
        if i + 1 < len(raw) and raw[i+1] != 0x0A:
            positions.append(i)
        elif i + 1 >= len(raw):
            positions.append(i)

print("Found %d bare CR characters" % len(positions))
for pos in positions[:20]:  # Show first 20
    ctx = raw[max(0,pos-20):pos+30]
    print("  byte %d: %s" % (pos, repr(ctx.decode('utf-8', errors='replace'))))

# Also show count of CRLF
crlf_count = raw.count(b'\r\n')
print("\nCRLF count: %d" % crlf_count)

# Strategy: Remove all bare CR characters (replace with empty)
# In JSON strings, \r should be escaped as \\r anyway
print("\n=== Removing bare CR characters ===")
new_raw = bytearray(raw)
removed = 0
for i in range(len(new_raw)-1, -1, -1):
    if new_raw[i] == 0x0D:
        if i + 1 >= len(new_raw) or new_raw[i+1] != 0x0A:
            # Bare CR - remove it
            del new_raw[i]
            removed += 1

print("Removed %d bare CR characters" % removed)

# Save
with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(bytes(new_raw))
print("Saved!")

# Verify
try:
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    print("SUCCESS! %d cells" % len(nb['cells']))
    
    for i, cell in enumerate(nb['cells']):
        cell_type = cell.get('cell_type', 'unknown')
        src = cell.get('source', [])
        if isinstance(src, list):
            first_line = src[0].strip()[:60] if src else '(empty)'
        else:
            first_line = str(src)[:60]
        print("  Cell %d: %s | %s" % (i, cell_type, first_line))
        
except json.JSONDecodeError as e:
    print("Still broken: %s at line %d" % (e.msg, e.lineno))
