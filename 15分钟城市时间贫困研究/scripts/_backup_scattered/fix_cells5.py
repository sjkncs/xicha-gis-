import json

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'

with open(filepath, 'r', encoding='utf-8') as f:
    nb = json.load(f)

print(f"Before: {len(nb['cells'])} cells")

# Fix 1: Change cell 26 from markdown to code
cell26 = nb['cells'][26]
print(f"\nCell 26 type: {cell26['cell_type']}")
cell26['cell_type'] = 'code'
cell26['execution_count'] = None
print(f"Changed to: {cell26['cell_type']}")

# Fix 2: Remove cell 27 (duplicate 6b header) — it duplicates cell 25
# Actually let's just overwrite cell 27 with the proper Moran's I section header
# Wait, cell 28 is already the Moran's I code... let me just delete cell 27
del nb['cells'][27]
print(f"\nAfter deletion: {len(nb['cells'])} cells")

# Verify the sequence
print("\nFinal cell sequence:")
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', ['']))
    first_line = src.split('\n')[0][:60] if src else '(empty)'
    print(f"Cell {i:2d} | {cell['cell_type']:8s} | {first_line}")

# Save
with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)
print("\nSaved successfully!")
