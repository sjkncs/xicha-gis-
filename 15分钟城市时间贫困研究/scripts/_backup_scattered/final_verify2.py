import json, ast

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    nb = json.load(f)

print(f"Notebook: {len(nb['cells'])} cells")

code_cells = [(i, ''.join(c.get('source',['']))) for i,c in enumerate(nb['cells']) if c['cell_type']=='code']
md_cells = [(i, ''.join(c.get('source',['']))) for i,c in enumerate(nb['cells']) if c['cell_type']=='markdown']
print(f"Code cells: {len(code_cells)}, Markdown cells: {len(md_cells)}")

errors = []
for i, src in code_cells:
    lines = src.split('\n')
    # Check for real syntax errors (not !pip install magic)
    real_lines = [l for l in lines if not (l.strip().startswith('!') and 'pip install' in l)]
    test_src = '\n'.join(real_lines)
    try:
        ast.parse(test_src)
    except SyntaxError as e:
        # Only flag if it's not related to shell magic
        err_line = lines[e.lineno-1] if e.lineno <= len(lines) else ''
        if not ('!' in err_line and 'pip' in err_line):
            errors.append((i, str(e)))

if errors:
    print(f"\n{len(errors)} cells with syntax errors:")
    for i, e in errors:
        print(f"  Cell {i}: {e}")
else:
    print("\nAll code cells have valid Python syntax!")

# Summary of new content
print("\n=== NEW CONTENT VERIFICATION ===")
new_ids = {11: '3b_intro', 12: '3b_code', 13: 'vuln_viz', 25: '6b_intro', 26: '6b_code', 34: 'policy'}
for idx, name in new_ids.items():
    if idx < len(nb['cells']):
        cell = nb['cells'][idx]
        src = ''.join(cell.get('source', ['']))
        has_content = len(src) > 50
        ctype = cell['cell_type']
        print(f"  {name} (cell {idx}): {ctype}, {len(src)} chars, has_content={has_content}")

print("\n=== JSON INTEGRITY ===")
try:
    test = json.dumps(nb)
    json.loads(test)
    print("  JSON integrity: VERIFIED")
except Exception as e:
    print(f"  JSON ERROR: {e}")

print("\nDone!")
