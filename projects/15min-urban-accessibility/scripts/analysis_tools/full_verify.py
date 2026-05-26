import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
print("=" * 70)
print("NOTEBOOK STRUCTURE (35 cells)")
print("=" * 70)
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    ctype = c.get('cell_type', '?')
    preview = src[:60].replace('\n', ' ').strip()
    print(f"  [{i:2d}] {ctype:8s} | {preview}")

# Check key integration points
print("\n" + "=" * 70)
print("KEY INTEGRATION POINTS")
print("=" * 70)
print("\n[Cell 6 - Village Data]:")
c = cells[6]
src = "".join(c.get('source', []))
print("  load_village_data:", "load_village_data" in src)
print("  communities_gdf:", "communities_gdf" in src)
print("  district_centroid:", "district_centroid" in src)
print("  geocode_status:", "geocode_status" in src)

print("\n[Cell 16 - 2SFCA Engine]:")
c = cells[16]
src = "".join(c.get('source', []))
print("  TwoStepFloatingCatchmentArea:", "TwoStepFloatingCatchmentArea" in src)
print("  communities_gdf:", "communities_gdf" in src)

print("\n[Cell 17 - OD Matrix]:")
c = cells[17]
src = "".join(c.get('source', []))
print("  build_od_matrix:", "build_od_matrix" in src)
print("  communities_gdf:", "communities_gdf" in src)
print("  center_lng:", "center_lng" in src)

print("\n[No simulate cell remaining]:")
found_sim = False
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    if "generate_communities_aoi" in src or ("Polygon" in src and "simulate" in src.lower()):
        print(f"  FOUND simulate cell at {i}!")
        found_sim = True
if not found_sim:
    print("  OK - no simulate cells found")
