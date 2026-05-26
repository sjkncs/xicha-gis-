import os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

base = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
files = [
    (base + r"\osm_data\nanshan_poi_integrated_v2.csv", "POI v2 CSV"),
    (base + r"\osm_data\nanshan_poi_integrated_v2.json", "POI v2 JSON"),
    (base + r"\building_data\nanshan_residential_buildings.geojson", "居住建筑 GeoJSON"),
    (base + r"\building_data\nanshan_buildings.gpkg", "建筑 GPKG"),
    (base + r"\building_data\nanshan_buildings_preview.png", "预览图 PNG"),
    (base + r"\osm_data\nanshan_villages_with_building.csv", "小区+建筑 CSV"),
]
for f, desc in files:
    exists = os.path.exists(f)
    if exists:
        size = os.path.getsize(f) / 1024 / 1024
        print("OK  {}: {:.1f} MB".format(desc, size))
    else:
        print("MISS  {}: NOT FOUND".format(desc))
