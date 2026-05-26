"""Read specific notebook cells"""
import json, io, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
for enc in ['utf-8', 'utf-8-sig', 'gbk', 'latin-1']:
    try:
        with open(nb, 'r', encoding=enc) as f:
            data = json.load(f)
        break
    except:
        pass

cells = data['cells']
print(f"Total cells: {len(cells)}")

# Read cells 10-18
for idx in [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]:
    c = cells[idx]
    src = "".join(c.get("source", []))
    print(f"\n{'='*70}")
    print(f"CELL {idx} [{c['cell_type']}]")
    print(f"{'='*70}")
    for ln in src.split('\n')[:80]:
        print(ln)
    if len(src.split('\n')) > 80:
        print(f"  ... ({len(src.split(chr(10)))} lines total)")
