# -*- coding: utf-8 -*-
import pandas as pd
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

print('='*70)
print('1. 住宅小区数据 (nanshan_villages_with_building.csv)')
print('='*70)
df = pd.read_csv('osm_data/nanshan_villages_with_building.csv')
print(f'总行数: {len(df)}')
print(f'列名: {list(df.columns)}')
print()
print('前3行数据:')
print(df.head(3).to_string())

print()
print('='*70)
print('2. 小区数据库 (sz_village_geocoded.csv)')
print('='*70)
df2 = pd.read_csv('village_data/sz_village_geocoded.csv')
print(f'总行数: {len(df2)}')
print(f'列名: {list(df2.columns)}')
if 'quxian' in df2.columns:
    nanshan = df2[df2['quxian'] == '南山'] if '南山' in df2['quxian'].values else df2[df2['quxian'].str.contains('南山', na=False)] if df2['quxian'].dtype == 'object' else df2[df2['quxian'].notna()]
    print(f'南山区小区数: {len(nanshan)}')

print()
print('='*70)
print('3. V5 夜间营业时间数据 (nanshan_poi_v5.csv)')
print('='*70)
df3 = pd.read_csv('osm_data/nanshan_poi_v5.csv', low_memory=False)
print(f'总行数: {len(df3)}')
print(f'列名: {list(df3.columns)}')
if 'night_service' in df3.columns:
    print('night_service 分布:')
    print(df3['night_service'].value_counts(dropna=False))

print()
print('='*70)
print('4. 整合后 POI 数据 - night_service_final')
print('='*70)
df4 = pd.read_csv('osm_data/nanshan_poi_integrated_v2.csv', low_memory=False)
print(f'总行数: {len(df4)}')
print(f'列名: {list(df4.columns)}')
if 'night_service_final' in df4.columns:
    print('night_service_final 分布:')
    print(df4['night_service_final'].value_counts(dropna=False))

print()
print('='*70)
print('5. OSM 建筑数据 (anshan_buildings_v2.geojson)')
print('='*70)
try:
    gdf = gpd.read_file('building_data/nanshan_buildings_v2.geojson')
    print(f'总建筑数: {len(gdf)}')
    print(f'列名: {list(gdf.columns)}')
    print(f'建筑类型分布:')
    print(gdf['building'].value_counts(dropna=False) if 'building' in gdf.columns else '无 building 列')
except Exception as e:
    print(f'读取失败: {e}')
