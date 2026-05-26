# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Show OSM POI cell (index 12)
cell12 = nb['cells'][12]
print("=== CELL 12 (OSM POI) ===")
for i, line in enumerate(cell12['source']):
    print(f"  {i:3d}: {repr(line)[:100]}")

# Check 2SFCA cell (index 16) for what columns poi_df needs
cell16 = nb['cells'][16]
src16 = ''.join(cell16['source'])
print("\n=== CELL 16 (2SFCA) - POI column references ===")
for i, line in enumerate(cell16['source']):
    if 'poi' in line.lower() and ('supply' in line.lower() or 'facility_type' in line.lower() or 'night_service' in line.lower() or 'weight' in line.lower()):
        print(f"  {i:3d}: {repr(line)[:120]}")

# Check NetworkDistanceCalculator cell (index 15) for poi_df usage
cell15 = nb['cells'][15]
print("\n=== CELL 15 (Network Distance) - POI column references ===")
for i, line in enumerate(cell15['source']):
    if 'poi' in line.lower() and ('lng' in line.lower() or 'lat' in line.lower() or 'facility' in line.lower()):
        print(f"  {i:3d}: {repr(line)[:120]}")
