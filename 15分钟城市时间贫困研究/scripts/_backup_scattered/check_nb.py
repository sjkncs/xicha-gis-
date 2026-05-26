# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# Check cell 7 (village load)
cell7 = nb['cells'][7]
src7 = ''.join(cell7['source'])
print("=== CELL 7 (village data) ===")
if 'community_type' not in src7 or 'isna().all()' in src7:
    print("  OK: Uses DB precomputed data")
else:
    print("  ISSUE: Still using random data")
# show last 10 lines
print("  Last 10 lines:")
for line in cell7['source'][-10:]:
    print(f"    {repr(line)[:80]}")

# Check road network cell (cell 8)
cell8 = nb['cells'][8]
src8 = ''.join(cell8['source'])
print("\n=== CELL 8 (road network) ===")
for line in cell8['source'][:5]:
    print(f"  {repr(line)[:80]}")
print("  ...")
for line in cell8['source'][-5:]:
    print(f"  {repr(line)[:80]}")

# Check if graphml_path uses cache or osm_data
for i, line in enumerate(cell8['source']):
    if 'graphml' in line or 'osm_cache' in line or 'road_network' in line:
        print(f"  Line {i}: {repr(line)[:100]}")

# Find POI cell
print("\n=== POI CELL ===")
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell.get('source', []))
    if 'poi_df' in src and 'facility_type' in src and len(src) > 2000:
        print(f"POI cell index: {i}")
        # show nanshan_poi references
        for j, line in enumerate(cell['source']):
            if 'nanshan_poi' in line:
                print(f"  Line {j}: {repr(line)[:100]}")
        break
