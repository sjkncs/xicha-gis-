import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
print(f"Total cells: {len(cells)}")
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    if 'village' in src.lower() or '搜房' in src or 'fang' in src.lower() or 'real village' in src.lower():
        print(f"\nCell {i} [{c['cell_type']}]:")
        print(src[:300])
