# -*- coding: utf-8 -*-
"""
南山区官方楼栋数据分析
- 正确UTF-8编码读取
- GCJ-02 -> WGS-84纠偏
- 使用用途分类统计
- 生成GeoJSON用于地图可视化
"""
import pandas as pd, os, io, sys, math, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
BDIR = os.path.join(BASE, "building_data")
src = [f for f in os.listdir(BDIR) if '楼栋' in f or '房屋' in f][0]
path = os.path.join(BDIR, src)
print(f"[1] Reading: {src}")

# ---- 1. 读取数据 (UTF-8) ----
df = pd.read_csv(path, encoding='utf-8')
df.columns = ['code', 'lon_gcj02', 'lat_gcj02', 'addr', 'name', 'pk',
               'use_type', 'update_year', 'floors', 'update_status']
print(f"    Rows: {len(df)}, Cols: {list(df.columns)}")

# ---- 2. 坐标范围验证 ----
print(f"\n[2] Coordinate ranges (GCJ-02):")
print(f"    lon: {df['lon_gcj02'].min():.6f} - {df['lon_gcj02'].max():.6f}")
print(f"    lat: {df['lat_gcj02'].min():.6f} - {df['lat_gcj02'].max():.6f}")
# Filter valid
valid = ((df['lon_gcj02'] >= 113.8) & (df['lon_gcj02'] <= 114.0) &
          (df['lat_gcj02'] >= 22.4) & (df['lat_gcj02'] <= 22.7))
df_v = df[valid].copy()
print(f"    Valid: {len(df_v)} / {len(df)} ({len(df)-len(df_v)} invalid)")

# ---- 3. GCJ-02 -> WGS-84 ----
def gcj02_to_wgs84(lng, lat):
    a, ee = 6378245.0, 0.00669342162296594323
    dlat = (-100 + 2*lng + 3*lat + 0.2*lat**2 + 0.1*lng*lat + 0.2*math.sqrt(abs(lng))) + \
           (20*math.sin(6*lng*math.pi) + 20*math.sin(2*lng*math.pi))*2/3 + \
           (20*math.sin(lat*math.pi) + 40*math.sin(lat/3*math.pi))*2/3 + \
           (160*math.sin(lat/12*math.pi) + 320*math.sin(lat/30*math.pi))*2/3
    dlon = (300 + lng + 2*lat + 0.1*lng**2 + 0.1*lng*lat + 0.1*math.sqrt(abs(lng))) + \
            (20*math.sin(6*lng*math.pi) + 20*math.sin(2*lng*math.pi))*2/3 + \
            (20*math.sin(lng*math.pi) + 40*math.sin(lng/3*math.pi))*2/3 + \
            (150*math.sin(lng/12*math.pi) + 300*math.sin(lng/30*math.pi))*2/3
    radlat = lat * math.pi / 180
    magic = 1 - ee * math.sin(radlat)**2
    dlat = dlat * 180 / ((a*(1-ee)) / (magic*math.sqrt(magic)) * math.pi)
    dlon = dlon * 180 / (a / math.sqrt(magic) * math.cos(radlat) * math.pi)
    return lng + dlon, lat + dlat

wl, wlt = [], []
for _, r in df_v.iterrows():
    l, lt = gcj02_to_wgs84(r['lon_gcj02'], r['lat_gcj02'])
    wl.append(l); wlt.append(lt)
df_v['wgs_lon'] = wl
df_v['wgs_lat'] = wlt
print(f"\n[3] After GCJ02->WGS84:")
print(f"    WGS lon: {df_v['wgs_lon'].min():.6f} - {df_v['wgs_lon'].max():.6f}")
print(f"    WGS lat: {df_v['wgs_lat'].min():.6f} - {df_v['wgs_lat'].max():.6f}")

# ---- 4. 使用用途 ----
USE_MAP = {
    1: '住宅/residential', 2: '商业/commercial', 3: '办公/office',
    4: '工业/industrial', 5: '公共/public', 6: '农业/agricultural',
    7: '混合/mixed', 8: '科教/education', 9: '其他/other'
}
df_v['use_name'] = df_v['use_type'].map(USE_MAP).fillna('未知/unknown')
print(f"\n[4] Use type distribution:")
for k, v in df_v['use_name'].value_counts().items():
    print(f"    {k}: {v}")

# ---- 5. 按南山区街道办范围过滤 ----
# Nanshan approx bounding box: 113.85-113.96 lon, 22.48-22.60 lat
ns_f = ((df_v['wgs_lon'] >= 113.85) & (df_v['wgs_lon'] <= 113.96) &
        (df_v['wgs_lat'] >= 22.48) & (df_v['wgs_lat'] <= 22.60))
df_ns = df_v[ns_f].copy()
print(f"\n[5] Within Nanshan bbox: {len(df_ns)} / {len(df_v)}")
print(f"    (bbox: 113.85-113.96E, 22.48-22.60N)")

# ---- 6. 楼栋密度分析 ----
print(f"\n[6] Building stats:")
print(f"    Total floors: {df_ns['floors'].sum():,} (sum of all building floors)")
print(f"    Avg floors/building: {df_ns['floors'].mean():.1f}")
print(f"    Floors range: {df_ns['floors'].min()} - {df_ns['floors'].max()}")
print(f"    High-rise (>10 floors): {(df_ns['floors']>10).sum()} buildings")

# ---- 7. 统计摘要 ----
print(f"\n[7] Summary stats:")
summary = {
    'total_buildings': len(df_v),
    'nanshan_buildings': len(df_ns),
    'floors_total': int(df_ns['floors'].sum()),
    'floors_mean': round(float(df_ns['floors'].mean()), 2),
    'floors_max': int(df_ns['floors'].max()),
    'wgs_lon_range': [round(float(df_ns['wgs_lon'].min()), 6), round(float(df_ns['wgs_lon'].max()), 6)],
    'wgs_lat_range': [round(float(df_ns['wgs_lat'].min()), 6), round(float(df_ns['wgs_lat'].max()), 6)],
    'use_type_counts': df_ns['use_name'].value_counts().to_dict(),
    'highrise_count': int((df_ns['floors'] > 10).sum()),
}
print(json.dumps(summary, ensure_ascii=False, indent=2))

# ---- 8. 保存清洗后的CSV ----
out_csv = os.path.join(BDIR, 'nanshan_buildings_official_wgs.csv')
out_cols = ['code', 'wgs_lon', 'wgs_lat', 'addr', 'name', 'pk',
            'use_type', 'use_name', 'update_year', 'floors', 'update_status',
            'lon_gcj02', 'lat_gcj02']
df_ns[out_cols].to_csv(out_csv, index=False, encoding='utf-8-sig')
print(f"\n[8] CSV saved: {out_csv}")

# ---- 9. GeoJSON ----
try:
    import geopandas as gpd
    from shapely.geometry import Point
    gdf = gpd.GeoDataFrame(
        df_ns,
        geometry=[Point(xy) for xy in zip(df_ns['wgs_lon'], df_ns['wgs_lat'])],
        crs='EPSG:4326'
    )
    geojson_out = os.path.join(BDIR, 'nanshan_buildings_official.geojson')
    gdf.to_file(geojson_out, driver='GeoJSON', encoding='utf-8')
    print(f"[9] GeoJSON saved: {geojson_out}")
except Exception as e:
    print(f"[9] GeoJSON failed: {e}")

print("\n*** DONE ***")
