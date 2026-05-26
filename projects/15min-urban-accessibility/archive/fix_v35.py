NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Read raw bytes
with open(NOTEBOOK_PATH, 'rb') as f:
    raw = bytearray(f.read())

print("File size: %d bytes" % len(raw))

# Find all bare CR (0x0D) that are NOT part of CRLF (0x0D 0x0A)
# In JSON, CR inside strings should be escaped as \r (0x5C 0x72)
# But bare CR before LF is fine (it's part of CRLF line ending)

# Strategy: Find CR not followed by LF, and escape them
removed = 0
fixed = 0
i = len(raw) - 1
while i >= 0:
    if raw[i] == 0x0D:
        # Check if it's followed by LF (part of CRLF)
        if i + 1 < len(raw) and raw[i+1] == 0x0A:
            # It's part of CRLF - OK
            i -= 1
            continue
        else:
            # Bare CR - escape it
            raw[i] = 0x5C  # Replace CR with \ (backslash)
            raw.insert(i + 1, 0x72)  # Insert r after \
            fixed += 1
    i -= 1

print("Fixed %d bare CR characters" % fixed)

# Save
with open(NOTEBOOK_PATH, 'wb') as f:
    f.write(raw)
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
    with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    for i in range(max(0, e.lineno-3), min(len(lines), e.lineno+2)):
        marker = ">>> " if i+1 == e.lineno else "    "
        print("%s%d: %s" % (marker, i+1, repr(lines[i])))
