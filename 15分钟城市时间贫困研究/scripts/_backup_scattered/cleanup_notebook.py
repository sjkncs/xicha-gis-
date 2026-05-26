import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"

with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
print(f"Total cells: {len(cells)}")

# Find and remove the old simulate cell (Cell 15: generate_communities_aoi + Polygon)
remove_idx = None
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    if 'generate_communities_aoi' in src and 'Polygon' in src:
        remove_idx = i
        print(f"\nOld simulate cell at index {i}:")
        print(src[:200])
        break

if remove_idx is None:
    print("Old simulate cell not found")
else:
    # Remove it
    cells.pop(remove_idx)
    print(f"\nRemoved cell at index {remove_idx}")
    print(f"Total cells now: {len(cells)}")

    # Save
    with open(nb, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print("Notebook saved")

    # Verify
    print("\nVerification - cells 5-8:")
    for i in range(max(0, remove_idx - 2), min(len(cells), remove_idx + 3)):
        c = cells[i]
        src = "".join(c.get('source', []))
        preview = src[:100].replace('\n', ' ')
        print(f"  [{i}] {c['cell_type']}: {preview}")
