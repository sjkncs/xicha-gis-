import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
for i in [5, 6, 7, 8, 14, 15, 16]:
    if i < len(cells):
        c = cells[i]
        src = "".join(c.get('source', []))
        print(f"\n{'='*60}")
        print(f"CELL {i} [{c.get('cell_type')}] - {len(src)} chars")
        print(src[:500])
        print("...")
