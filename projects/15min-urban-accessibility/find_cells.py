import json, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

print('Total cells: %d' % len(nb['cells']))

# Find all markdown cells with anchors or section headers
print('\n=== All section headers ===')
for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') == 'markdown':
        source = ''.join(cell.get('source', []))
        # Check for section headers
        match = re.search(r"##?\s*(\d+)[.。\s]", source)
        if match:
            section_num = match.group(1)
            preview = source[:100].replace('\n', ' ').replace('\r', '')[:80]
            print('Cell %d: Section %s - %s' % (i, section_num, preview))

# Find Fig11 related cells
print('\n=== Fig11 cells ===')
for i, cell in enumerate(nb['cells']):
    source_str = ''.join(cell.get('source', []))
    if 'Fig11' in source_str or '建筑AOI' in source_str:
        cell_type = cell.get('cell_type')
        preview = source_str[:100].replace('\n', ' ').replace('\r', '')[:80]
        print('Cell %d (%s): %s' % (i, cell_type, preview))

# Find the last code cell before Section 9 (anchor id=9)
print('\n=== Finding Section 9 ===')
sec9_idx = None
for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') == 'markdown':
        source = ''.join(cell.get('source', []))
        if "<a id='9'" in source:
            sec9_idx = i
            print('Section 9 found at cell %d' % i)
            break

# Find the last code cell before Section 9
if sec9_idx:
    for i in range(sec9_idx - 1, -1, -1):
        cell = nb['cells'][i]
        if cell.get('cell_type') == 'code':
            print('Last code cell before Section 9: cell %d' % i)
            source = ''.join(cell.get('source', []))
            # Find last print statement
            if 'print' in source:
                prints = re.findall(r"print\([^)]+\)", source)
                if prints:
                    print('  Last print: %s' % prints[-1][:60])
            break
