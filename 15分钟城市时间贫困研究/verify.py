import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)
print('SUCCESS! %d cells' % len(nb['cells']))

# Check first few cells
for i, cell in enumerate(nb['cells'][:5]):
    cell_type = cell.get('cell_type', 'unknown')
    if cell_type == 'markdown':
        source = ''.join(cell.get('source', []))
        preview = source[:60].replace('\n', ' ').replace('\r', '')
        print('Cell %d (markdown): %s' % (i, preview))
    else:
        print('Cell %d (code)' % i)

# Find key cells
print('\n=== Key cells ===')
for i, cell in enumerate(nb['cells']):
    cell_type = cell.get('cell_type', 'unknown')
    if cell_type == 'markdown':
        source = ''.join(cell.get('source', []))
        if '<a id=' in source:
            import re
            matches = re.findall(r"<a id='(\d+)'", source)
            if matches:
                print('Cell %d has anchor id=%s' % (i, matches[0]))
                print('  Content: %s' % source[:100].replace('\n', ' '))
