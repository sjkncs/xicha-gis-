import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("Total cells: %d" % len(nb['cells']))

# Find all section headers
print("\n=== All section headers ===")
for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') == 'markdown':
        source = ''.join(cell.get('source', []))
        match = re.search(r"##?\s*(\d+)[.。\s]|【(\d+)】", source)
        if match:
            section_num = match.group(1) or match.group(2)
            preview = source[:80].replace('\n', ' ').replace('\r', '')[:60]
            print("Cell %d: Section %s - %s" % (i, section_num, preview))

# Find Section 10 and after
print("\n=== Section 10 and beyond ===")
for i in range(35, len(nb['cells'])):
    cell = nb['cells'][i]
    cell_type = cell.get('cell_type')
    source = ''.join(cell.get('source', []))
    preview = source[:100].replace('\n', ' ').replace('\r', '')[:60]
    print("Cell %d (%s): %s" % (i, cell_type, preview))
