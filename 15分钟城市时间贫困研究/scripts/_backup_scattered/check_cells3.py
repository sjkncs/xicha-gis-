import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Check current state
print("Current cell structure:")
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', ['']))
    first_line = src.split('\n')[0][:60] if src else '(empty)'
    print(f"Cell {i:2d} | {cell['cell_type']:8s} | {first_line}")

print("\n--- Checking cell 26 (equity code cell) ---")
cell26 = nb['cells'][26]
print(f"Type: {cell26['cell_type']}")
src26 = ''.join(cell26.get('source', ['']))
print(f"Length: {len(src26)}")
print(f"Preview: {repr(src26[:100])}")
