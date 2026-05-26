import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Check cells 25-27 in detail
for i in [25, 26, 27]:
    cell = nb['cells'][i]
    src = ''.join(cell.get('source', ['']))
    print(f"=== Cell {i} ({cell['cell_type']}) ===")
    print(src[:500])
    print("...\n")
