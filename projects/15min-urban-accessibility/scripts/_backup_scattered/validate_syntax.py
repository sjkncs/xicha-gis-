import json, ast, sys

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

errors = []
for i, cell in enumerate(nb['cells']):
    if cell['cell_type'] == 'code':
        src = ''.join(cell.get('source', ['']))
        try:
            ast.parse(src)
            print(f"Cell {i:2d}: OK")
        except SyntaxError as e:
            errors.append((i, str(e)))
            print(f"Cell {i:2d}: SYNTAX ERROR - {e}")

if errors:
    print(f"\n{len(errors)} cells have syntax errors!")
else:
    print(f"\nAll {sum(1 for c in nb['cells'] if c['cell_type']=='code')} code cells have valid syntax!")
    print("Notebook is ready for execution.")
