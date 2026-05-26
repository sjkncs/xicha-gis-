import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f"Notebook: {len(nb['cells'])} cells")
print()
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', ['']))
    first_line = src.split('\n')[0][:70] if src else '(empty)'
    print(f"Cell {i:2d} | {cell['cell_type']:8s} | {first_line}")
