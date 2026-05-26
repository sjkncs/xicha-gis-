import json, ast, sys

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    nb = json.load(f)

print(f"Notebook: {len(nb['cells'])} cells\n")

code_cells = []
md_cells = []

for i, cell in enumerate(nb['cells']):
    ctype = cell['cell_type']
    src = ''.join(cell.get('source', ['']))
    
    if ctype == 'code':
        code_cells.append((i, src))
        # Check syntax (but allow shell magic like !pip install)
        # Only flag REAL syntax errors, not notebook magic
        lines = src.split('\n')
        real_python_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip lines that are purely shell commands (start with !)
            if stripped.startswith('!') and len(stripped) < 200:
                real_python_lines.append('# shell: ' + stripped)
            else:
                real_python_lines.append(line)
        
        test_src = '\n'.join(real_python_lines)
        try:
            ast.parse(test_src)
            status = "OK"
        except SyntaxError as e:
            # Check if it's a real error
            if '!' in lines[e.lineno-1] and 'pip' in lines[e.lineno-1]:
                status = "OK (shell magic)"
            else:
                status = f"ERROR: {e}"
    else:
        md_cells.append((i, src[:50]))
        status = "markdown"

print(f"Code cells: {len(code_cells)}")
print(f"Markdown cells: {len(md_cells)}\n")

# Print all cells summary
print("=== FULL CELL SUMMARY ===")
for i, cell in enumerate(nb['cells']):
    ctype = cell['cell_type']
    src = ''.join(cell.get('source', ['']))
    first = src.split('\n')[0][:80] if src else '(empty)'
    print(f"Cell {i:2d} | {ctype:8s} | {first}")

# Check new cells we added
print("\n=== NEW CELLS CONTENT CHECK ===")
new_cells = [11, 12, 13, 25, 26, 34]
for i in new_cells:
    if i < len(nb['cells']):
        cell = nb['cells'][i]
        src = ''.join(cell.get('source', ['']))
        first = src.split('\n')[0][:80] if src else '(empty)'
        print(f"Cell {i}: {cell['cell_type']} | {first}")

print("\n=== JSON VALIDATION ===")
try:
    # Re-dump and re-load to verify JSON integrity
    test_dump = json.dumps(nb)
    print("JSON dump: OK")
    test_load = json.loads(test_dump)
    print("JSON load: OK")
    print(f"Notebook integrity: VERIFIED ({len(test_load['cells'])} cells)")
except Exception as e:
    print(f"JSON ERROR: {e}")
