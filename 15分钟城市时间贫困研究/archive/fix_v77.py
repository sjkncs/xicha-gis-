NOTEBOOK_PATH = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

import sys, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(NOTEBOOK_PATH, 'rb') as f:
    raw = f.read()

text = raw.decode('utf-8', errors='replace')
lines = text.split('\n')

print("=== File beginning (lines 1-10) ===")
for i in range(min(10, len(lines))):
    print("Line %d: %s" % (i+1, repr(lines[i][:80])))

print("\n=== Looking for Section 9 ===")
for i, line in enumerate(lines):
    if 'Section 9' in line or '第9' in line or 'section_9' in line.lower():
        print("Line %d: %s" % (i+1, repr(line.strip())))
        
print("\n=== Looking for Fig11 cell ===")
for i, line in enumerate(lines):
    if 'Fig11' in line and 'cell_type' not in line:
        print("Line %d: %s" % (i+1, repr(line.strip()[:80])))

print("\n=== Cell structure (lines 3050-3330) ===")
in_cell = False
for i in range(3049, min(3330, len(lines))):
    stripped = lines[i].strip()
    if '"cell_type"' in stripped:
        print("Line %d: %s" % (i+1, repr(stripped[:80])))
        in_cell = True
    if stripped == '},':
        print("Line %d: %s" % (i+1, repr(stripped)))
    if stripped == '],' and in_cell:
        print("Line %d: %s" % (i+1, repr(stripped)))
        in_cell = False

# Check how many total cells and lines
print("\n=== File stats ===")
print("Total lines: %d" % len(lines))
print("Total LFs: %d" % raw.count(b'\n'))
print("Total CRs: %d" % raw.count(b'\r'))
print("File size: %d bytes" % len(raw))

# Try to count cells
print("\n=== Cell count ===")
cell_count = text.count('"cell_type"')
print("Cells found: %d" % cell_count)
