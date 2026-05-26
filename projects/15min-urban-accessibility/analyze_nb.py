# -*- coding: utf-8 -*-
import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']
total = len(cells)
code_cells = [c for c in cells if c['cell_type'] == 'code']
md_cells = [c for c in cells if c['cell_type'] == 'markdown']

print(f'Total cells: {total}')
print(f'Code cells: {len(code_cells)}')
print(f'Markdown cells: {len(md_cells)}')
print()

executed = [c for c in code_cells if c.get('execution_count') is not None]
not_executed = [c for c in code_cells if c.get('execution_count') is None]
has_output = [c for c in code_cells if c.get('outputs') and len(c.get('outputs', [])) > 0]

print(f'Executed (execution_count not null): {len(executed)}')
print(f'Not executed (execution_count null): {len(not_executed)}')
print(f'Has non-empty outputs: {len(has_output)}')
print()

print('=' * 80)
print('ALL CODE CELLS STATUS')
print('=' * 80)
for i, c in enumerate(code_cells):
    ec = c.get('execution_count')
    outputs = c.get('outputs', [])
    has_out = len(outputs) > 0
    source_lines = [l.strip() for l in c.get('source', []) if l.strip()]
    
    first_comment = None
    for line in source_lines:
        if line.startswith('#') and len(line) > 3:
            first_comment = line.strip()
            break
    
    source_text = ''.join(c.get('source', []))
    has_folium = 'folium' in source_text.lower()
    
    status = 'EXECUTED' if ec is not None else 'NOT_EXECUTED'
    output_status = 'HAS_OUTPUT' if has_out else 'NO_OUTPUT'
    
    print(f'Code Cell #{i+1}: [{status}] [{output_status}]')
    if first_comment:
        print(f'  Title: {first_comment[:120]}')
    if has_folium:
        print(f'  >>> FOLIUM CELL <<<')
    if not has_out and ec is None:
        print(f'  (empty, never run)')
    print()

# Folium cells
print('=' * 80)
print('FOLIUM CELLS ONLY')
print('=' * 80)
folium_count = 0
for i, c in enumerate(code_cells):
    source_text = ''.join(c.get('source', []))
    if 'folium' in source_text.lower():
        folium_count += 1
        ec = c.get('execution_count')
        status = 'EXECUTED' if ec is not None else 'NOT_EXECUTED'
        outputs = c.get('outputs', [])
        print(f'Code Cell #{i+1}: [{status}] [outputs={len(outputs)}]')
        for line in c.get('source', []):
            if line.strip().startswith('#') and len(line.strip()) > 5:
                print(f'  Title: {line.strip()[:120]}')
                break
        print()

print(f'Total Folium cells: {folium_count}')

# Section 8 check
print('=' * 80)
print('SECTION 8 (交互可视化 Folium) CHECK')
print('=' * 80)
in_section8 = False
section8_cells = []
for i, c in enumerate(cells):
    if c['cell_type'] == 'markdown':
        src = ''.join(c.get('source', []))
        if '## 8.' in src or '交互可视化' in src or '#8' in src or 'folium' in src.lower():
            in_section8 = True
    if in_section8 and c['cell_type'] == 'code':
        section8_cells.append((i+1, c))
        ec = c.get('execution_count')
        status = 'EXECUTED' if ec is not None else 'NOT_EXECUTED'
        print(f'  Cell {i+1}: [{status}]')

print(f'\nTotal Section 8 cells: {len(section8_cells)}')
print(f'  Executed: {sum(1 for _,c in section8_cells if c.get("execution_count") is not None)}')
print(f'  Not executed: {sum(1 for _,c in section8_cells if c.get("execution_count") is None)}')
