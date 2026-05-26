import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
print(f"Total cells: {len(cells)}")
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    ctype = c.get('cell_type', '?')
    preview = src[:80].replace('\n', ' ')[:80]
    print(f"  [{i:2d}] {ctype:8s} | {preview}")
