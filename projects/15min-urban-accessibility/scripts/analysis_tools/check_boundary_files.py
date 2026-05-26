# -*- coding: utf-8 -*-
import geopandas as gpd
import os

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

print("=" * 60)
print("检查项目中的所有地理边界文件")
print("=" * 60)

# 扫描所有可能包含边界数据的文件
all_files = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        ext = f.lower()
        if any(ext.endswith(e) for e in ['.geojson', '.json', '.shp', '.gpkg', '.topojson']):
            if not any(s in root for s in ['广东省', 'POI', 'poi']):
                all_files.append(os.path.join(root, f))

print(f"\n找到 {len(all_files)} 个地理数据文件:\n")
for fp in all_files:
    rel = fp.replace(BASE, '').lstrip('\\').lstrip('/')
    try:
        gdf = gpd.read_file(fp)
        geom_type = gdf.geom_type.iloc[0] if len(gdf) > 0 else 'empty'
        print(f"  {rel}")
        print(f"    Shape: {gdf.shape}, Geometry: {geom_type}, CRS: {gdf.crs}")
        # 检查是否是面/多边形
        if geom_type in ['Polygon', 'MultiPolygon']:
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            print(f"    Bounds: lon [{bounds[0]:.4f}, {bounds[2]:.4f}], lat [{bounds[1]:.4f}, {bounds[3]:.4f}]")
            # 判断是否是南山区 (lon ~113.85-114.05, lat ~22.45-22.65)
            lon_ok = 113.8 < bounds[0] < 114.1 and 113.8 < bounds[2] < 114.1
            lat_ok = 22.4 < bounds[1] < 22.7 and 22.4 < bounds[3] < 22.7
            if lon_ok and lat_ok:
                print(f"    [可能是南山区边界]")
            else:
                print(f"    [非南山区]")
        print()
    except Exception as e:
        print(f"  {rel}  [ERROR: {e}]")

print("\n" + "=" * 60)
print("检查 village_data 目录")
print("=" * 60)
vd = os.path.join(BASE, 'village_data')
if os.path.exists(vd):
    for f in os.listdir(vd):
        print(f"  {f}")
else:
    print("  [目录不存在]")
