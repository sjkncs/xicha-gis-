# -*- coding: utf-8 -*-
"""
精确筛选南山区 POI
1. 读取南山区多边形（投影坐标系 -> WGS84）
2. 用 shapely 逐点做包含检测
3. 输出含营业时间的南山区 POI
"""
import shapefile, os, sys
import math
from shapely.geometry import Point, Polygon
import shapely

sys.stdout.reconfigure(encoding='utf-8')

# ====== 坐标系转换：Web Mercator -> WGS84 ======
def mercator_to_wgs84(x, y):
    """将Web Mercator投影坐标转回WGS84经纬度"""
    lon = (x / 20037508.34) * 180
    lat = (y / 20037508.34) * 180
    lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)
    return lon, lat

# ====== 读取南山区多边形 ======
district_shp = r"E:\xicha gis 智能定位\GData2\区级边界New.shp"
sf_d = shapefile.Reader(district_shp, encoding='utf-8')
shapes_d = list(sf_d.iterShapes())
recs_d = list(sf_d.fields)

# 找南山区 (索引3)
NANSHAN_IDX = 3
nanshan_shape = shapes_d[NANSHAN_IDX]

print(f"南山区原始多边形点数: {len(nanshan_shape.points)}")

# 转换多边形为WGS84坐标
nanshan_points_wgs84 = []
for pt in nanshan_shape.points:
    lon, lat = mercator_to_wgs84(pt[0], pt[1])
    nanshan_points_wgs84.append((lon, lat))

print(f"转换后WGS84范围:")
lons = [p[0] for p in nanshan_points_wgs84]
lats = [p[1] for p in nanshan_points_wgs84]
print(f"  Lon: {min(lons):.4f} ~ {max(lons):.4f}")
print(f"  Lat: {min(lats):.4f} ~ {max(lats):.4f}")

nanshan_polygon = Polygon(nanshan_points_wgs84)
print(f"南山区多边形面积（近似）: {nanshan_polygon.area:.4f} sq degree")

# ====== 读取POI并筛选 ======
poi_shp = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\poi.shp"
sf_p = shapefile.Reader(poi_shp, encoding='utf-8')
poi_fields = [f[0] for f in sf_p.fields[1:]]

print(f"\n=== 筛选南山区POI ===")
print(f"总POI数: {sf_p.numRecords}")

nanshan_pois = []
nanshan_with_hours = []

for i, shape in enumerate(sf_p.iterShapes()):
    # shape.points[0] 是点的 (lon, lat)
    pt = shape.points[0]
    lon, lat = pt[0], pt[1]
    rec = dict(zip(poi_fields, sf_p.record(i)))
    
    poi_point = Point(lon, lat)
    
    if nanshan_polygon.contains(poi_point):
        nanshan_pois.append({
            'lon': lon, 'lat': lat,
            'name': rec.get('name', ''),
            'shop': rec.get('shop', ''),
            'opening_hours': rec.get('opening_ho', ''),
            'brand': rec.get('brand', ''),
            'amenity': rec.get('amenity', ''),
            'addr_distr': rec.get('addr_distr', ''),
            'cuisine': rec.get('cuisine', ''),
        })
        
        hours = rec.get('opening_ho', '').strip()
        if hours:
            nanshan_with_hours.append({
                'lon': lon, 'lat': lat,
                'name': rec.get('name', ''),
                'shop': rec.get('shop', ''),
                'opening_hours': hours,
                'brand': rec.get('brand', ''),
                'amenity': rec.get('amenity', ''),
            })

print(f"南山区内POI: {len(nanshan_pois)}")
print(f"其中有营业时间: {len(nanshan_with_hours)}")

# ====== 输出结果 ======
out_dir = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data"

# 输出所有南山区POI
all_out = os.path.join(out_dir, "nanshan_poi_all.csv")
with open(all_out, 'w', encoding='utf-8-sig', newline='') as f:
    header = "lon,lat,name,shop,opening_hours,brand,amenity,addr_distr,cuisine\n"
    f.write(header)
    for p in nanshan_pois:
        line = f'{p["lon"]},{p["lat"]},{p["name"]},{p["shop"]},{p["opening_hours"]},{p["brand"]},{p["amenity"]},{p["addr_distr"]},{p["cuisine"]}\n'
        f.write(line)
print(f"\n已输出: {all_out}")

# 输出有营业时间的南山区POI
hours_out = os.path.join(out_dir, "nanshan_poi_with_hours.csv")
with open(hours_out, 'w', encoding='utf-8-sig', newline='') as f:
    header = "lon,lat,name,shop,opening_hours,brand,amenity\n"
    f.write(header)
    for p in nanshan_with_hours:
        line = f'{p["lon"]},{p["lat"]},{p["name"]},{p["shop"]},{p["opening_hours"]},{p["brand"]},{p["amenity"]}\n'
        f.write(line)
print(f"已输出: {hours_out}")

# 打印营业时间样本
print(f"\n=== 南山区POI样本 (前10条) ===")
for p in nanshan_pois[:10]:
    print(f"  [{p['lon']:.5f}, {p['lat']:.5f}] {p['name']} | shop={p['shop']} | hours={p['opening_hours']}")

print(f"\n=== 有营业时间的POI (共{len(nanshan_with_hours)}条) ===")
for p in nanshan_with_hours:
    print(f"  [{p['lon']:.5f}, {p['lat']:.5f}] {p['name']} ({p['shop']}) | {p['opening_hours']}")
