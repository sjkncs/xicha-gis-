# -*- coding: utf-8 -*-
import json

with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']
code_cells = [c for c in cells if c['cell_type'] == 'code']

print('=' * 80)
print('CODE CELL TITLES (Better Extraction)')
print('=' * 80)
for i, c in enumerate(code_cells):
    ec = c.get('execution_count')
    outputs = c.get('outputs', [])
    status = 'EXECUTED' if ec is not None else 'NOT_EXECUTED'
    has_out = len(outputs) > 0
    
    source_lines = [l.strip() for l in c.get('source', []) if l.strip()]
    
    # Find meaningful title - look for comment lines that describe the cell
    title = None
    for line in source_lines:
        if line.startswith('#') and len(line) > 5 and not line.startswith('# ===') and not line.startswith('# -*-'):
            title = line.strip()
            break
        if 'Cell:' in line and '修正' in line:
            title = line.strip()
            break
    
    # Also check for specific patterns
    source_text = ''.join(c.get('source', []))
    
    # Try to find section-like title from first non-comment line
    if not title:
        for line in source_lines:
            if not line.startswith('#') and len(line) > 10:
                title = f'(code): {line[:80]}'
                break
    
    if not title:
        title = '(no identifiable title)'
    
    has_folium = 'folium' in source_text.lower()
    
    print(f'\nCode Cell #{i+1}: [{status}] [outputs={len(outputs)}]')
    print(f'  Title: {title[:120]}')
    if has_folium:
        print(f'  *** FOLIUM CELL ***')
    
    # Print first 3 lines of source for context
    for j, line in enumerate(source_lines[:3]):
        if line.startswith('# ==='):
            continue
        print(f'  Line {j+1}: {line[:100]}')
    print()

# Now let's identify section boundaries from markdown cells
print('\n' + '=' * 80)
print('NOTEBOOK SECTION STRUCTURE (from markdown cells)')
print('=' * 80)
for i, c in enumerate(cells):
    if c['cell_type'] == 'markdown':
        src = ''.join(c.get('source', []))
        if src.strip().startswith('##'):
            print(f'MD Cell #{i+1}: {src.strip()[:120]}')
        elif '## ' in src:
            lines = src.split('\n')
            for line in lines:
                if line.strip().startswith('## '):
                    print(f'MD Cell #{i+1}: {line.strip()[:120]}')
                    break
