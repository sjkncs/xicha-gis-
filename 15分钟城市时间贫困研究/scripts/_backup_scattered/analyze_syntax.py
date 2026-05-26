"""Analyze all syntax errors in the notebook"""
import json, sys, io, ast
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print("=" * 70)
print("NOTEBOOK SYNTAX ANALYSIS")
print("=" * 70)

error_count = 0
fixes_needed = []

for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') != 'code':
        continue
    
    src = ''.join(cell.get('source', ''))
    if not src.strip():
        continue
    
    # Skip pure comments/shell
    stripped = src.strip()
    if stripped.startswith('#') or stripped.startswith('!'):
        continue
    
    # Try to parse as Python
    try:
        ast.parse(src)
        status = "OK"
    except SyntaxError as e:
        error_count += 1
        status = "ERROR: " + str(e)[:80]
        fixes_needed.append({
            'cell': i,
            'error': e,
            'src': src
        })
    
    first = src.split('\n')[0][:60]
    print("Cell " + str(i).rjust(2) + " | " + status[:60])
    if "ERROR" in status:
        print("        Line " + str(e.lineno) + ": " + str(e.msg))
        print("        -> " + src.split('\n')[e.lineno-1].strip()[:80])

print()
print("=" * 70)
print("Total syntax errors: " + str(error_count))

if fixes_needed:
    print("\nCELLS NEEDING FIXES:")
    for fix in fixes_needed:
        e = fix['error']
        src = fix['src']
        print("\n--- Cell " + str(fix['cell']) + " ---")
        print("Error: " + str(e))
        print("Problem line:")
        lines = src.split('\n')
        for j, line in enumerate(lines):
            if j == e.lineno - 1:
                print("  " + line.strip()[:100])
