import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

filepath = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb'
with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
    nb = json.load(f)

# Detailed check of cells 11-13
for idx in [11, 12, 13]:
    cell = nb['cells'][idx]
    ctype = cell['cell_type']
    src = ''.join(cell.get('source', ['']))
    print(f"\n=== Cell {idx} ===")
    print(f"  cell_type: {ctype}")
    print(f"  source length: {len(src)}")
    print(f"  first 200 chars: {src[:200]}")

# Detailed check of cells 25-26
for idx in [25, 26]:
    cell = nb['cells'][idx]
    ctype = cell['cell_type']
    src = ''.join(cell.get('source', ['']))
    print(f"\n=== Cell {idx} ===")
    print(f"  cell_type: {ctype}")
    print(f"  source length: {len(src)}")
    print(f"  first 200 chars: {src[:200]}")

# Check cell 34
cell = nb['cells'][34]
ctype = cell['cell_type']
src = ''.join(cell.get('source', ['']))
print(f"\n=== Cell 34 ===")
print(f"  cell_type: {ctype}")
print(f"  source length: {len(src)}")
print(f"  first 200 chars: {src[:200]}")
