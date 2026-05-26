NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

# Check lines around 3314-3320
print("=== Lines 3312-3325 ===")
for i in range(3311, min(3325, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i])))

# Count cell_type occurrences AFTER line 3072 (start of last cell)
print("\n=== Cell types in last cell (after line 3072) ===")
cell_count = 0
for i in range(3071, len(lines)):
    if '"cell_type"' in lines[i]:
        cell_count += 1
        print("Line %d: %s" % (i+1, repr(lines[i].strip())))
print("Total cells in last 'cell': %d" % cell_count)

# Check: are there any '},' that would close a cell BEFORE line 3315?
print("\n=== Cell-closing markers after line 3072 ===")
for i in range(3071, 3320):
    stripped = lines[i].strip()
    if stripped == '},' or stripped == '  },' or stripped == '   },':
        print("Line %d: %s" % (i+1, repr(stripped)))

# Let me look at lines 3066-3080 to understand cell structure before the last cell
print("\n=== Lines 3066-3085 ===")
for i in range(3065, 3085):
    print("Line %d: %s" % (i+1, repr(lines[i])))
