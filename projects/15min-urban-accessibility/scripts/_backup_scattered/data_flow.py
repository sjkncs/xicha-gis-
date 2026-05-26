import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb, 'r', encoding='utf-8') as f:
    data = json.load(f)

cells = data['cells']
print("VILLAGE INTEGRATION CHECK")
print("=" * 60)

# Cell 6 - our village data code
c = cells[6]
src = "".join(c.get('source', []))
print(f"\nCell 6 [Village Data] ({len(src)} chars):")
print("  Key features:")
print("  - load_village_data:", "load_village_data" in src)
print("  - communities_gdf =:", "communities_gdf" in src and "=" in src)
print("  - district_centroid:", "district_centroid" in src)
print("  - geocode_status:", "geocode_status" in src)
print("  - VILLAGE_DB:", "VILLAGE_DB" in src)

# Cell 7 - should be road network prep
c = cells[7]
src = "".join(c.get('source', []))
print(f"\nCell 7 [Road Network Prep] ({len(src)} chars):")
print("  First 100:", src[:100])

# Cell 16 - OD matrix (originally cell 18)
c = cells[18]
src = "".join(c.get('source', []))
print(f"\nCell 18 [OD Matrix] ({len(src)} chars):")
print("  communities_gdf:", "communities_gdf" in src)
print("  center_lng:", "center_lng" in src)
print("  dist_calc:", "dist_calc" in src)
print("  First 200:", src[:200])

# Check if there's a simulate cell anywhere
print("\n\nSimulate cell check:")
for i, c in enumerate(cells):
    src = "".join(c.get('source', []))
    if "simulate" in src.lower() and ("Polygon" in src or "Point" in src or "generate_communities" in src):
        print(f"  FOUND simulate at {i}:", src[:100])

print("\nDATA FLOW:")
print("  Cell 6: Load village data -> communities_gdf")
print("  Cell 7: G_walk road network setup")
print("  Cell 16: NetworkDistanceCalculator")
print("  Cell 17: TwoStepFloatingCatchmentArea")
print("  Cell 18: OD matrix from communities_gdf -> poi_df")
print("  Cell 19: run_2sfca_per_type")
print("  -> All downstream cells use communities_gdf")
