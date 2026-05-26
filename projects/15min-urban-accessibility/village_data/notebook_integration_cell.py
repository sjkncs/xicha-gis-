# ============================================================================
# 【替换模拟数据】搜房真实小区数据加载
# 数据来源: fang_2017-08-02.sql (搜房网2017年深圳小区数据)
# 数据库: village_data\villages.db
# ============================================================================
#
# 小区类型推断规则:
#   urban_village (城中村): 单价 < 25000元/平米 或名称含"村/城中村"
#   affordable_housing (保障房): 单价 25000-45000元/平米
#   commodity_housing (商品房): 单价 45000-80000元/平米
#   high_end (高端社区): 单价 > 80000元/平米
#
# 字段说明:
#   housetitle -> name (小区名)
#   center_lng/center_lat (中心点坐标，与 2SFCA 兼容)
#   community_type (小区类型)
#   population (人口估算，实际需接统计局)
#   built_year (建成年份估算，实际需接住建局)
#   area_m2 (占地面积估算，实际需接规划局)
#   supply (供给指标，实际需大众点评评分)
#
# 依赖: geopandas, shapely, pandas, numpy, sqlite3
# 安装: pip install geopandas pandas numpy shapely

import os, sys, sqlite3
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

VILLAGE_DB = r"e:\\xicha gis 智能定位\\15分钟城市时间贫困研究\\village_data\\villages.db"

# 区域中心用于无坐标时估算
DISTRICT_CENTROIDS = {
    '宝安': (113.8828, 22.5553), '龙岗': (114.2471, 22.7205),
    '南山': (113.9308, 22.5332), '福田': (114.0579, 22.5435),
    '罗湖': (114.1317, 22.5482), '盐田': (114.2361, 22.5557),
    '光明': (113.9297, 22.7623), '坪山': (114.3507, 22.6802),
    '龙华': (114.0495, 22.7149), '大鹏': (114.4871, 22.5817),
}
PRICE_THRESHOLDS = [
    (0, 25000, 'urban_village'), (25000, 45000, 'affordable_housing'),
    (45000, 80000, 'commodity_housing'), (80000, float('inf'), 'high_end'),
]
URBAN_VILLAGE_KEYWORDS = ['村', '城中村', '旧村', '新村', '居民点']

def infer_community_type(name, price):
    if isinstance(name, str):
        for kw in URBAN_VILLAGE_KEYWORDS:
            if kw in name:
                return 'urban_village'
    price = float(price) if price else 0
    for lo, hi, ctype in PRICE_THRESHOLDS:
        if lo <= price < hi:
            return ctype
    return 'high_end'

def load_village_data(db_path, require_coords=True):
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        print("  Run geocode_nominatim.py or geocode_amap.py first")
        return None
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM sz_village", conn)
    conn.close()
    print(f"SQLite records: {len(df)}")
    n_geo = df['lng'].notna().sum()
    print(f"With coordinates: {n_geo} / {len(df)}")
    if require_coords:
        df_work = df.dropna(subset=['lng', 'lat']).copy()
        df_work = df_work[
            (df_work['lng'] > 113.0) & (df_work['lng'] < 114.8) &
            (df_work['lat'] > 22.0) & (df_work['lat'] < 23.0)
        ].copy()
        print(f"Valid records: {len(df_work)}")
    else:
        def rough_coords(row):
            quxian = str(row.get('quxian', ''))
            for d, (lng, lat) in DISTRICT_CENTROIDS.items():
                if d in quxian:
                    return pd.Series([lng + np.random.uniform(-0.01, 0.01),
                                      lat + np.random.uniform(-0.01, 0.01)])
            return pd.Series([None, None])
        coords = df.apply(rough_coords, axis=1)
        df['lng'] = df['lng'].fillna(coords[0])
        df['lat'] = df['lat'].fillna(coords[1])
        df_work = df.copy()
        print("[NOTE] Using district centroids for missing coords")
    if len(df_work) == 0:
        print("[ERROR] No valid records! Check geocoding results.")
        return None
    df_work['community_type'] = df_work.apply(
        lambda r: infer_community_type(r['housetitle'], r['money']), axis=1
    )
    geometry = [Point(xy) for xy in zip(df_work['lng'], df_work['lat'])]
    gdf = gpd.GeoDataFrame(df_work, geometry=geometry, crs='EPSG:4326')
    gdf = gdf.rename(columns={
        'housetitle': 'name', 'sqpinyin': 'area_pinyin',
        'address': 'full_address', 'shangquan': 'business_district',
    })
    gdf['center_lng'] = gdf['lng']
    gdf['center_lat'] = gdf['lat']
    gdf = gdf.reset_index(drop=True)
    gdf['community_id'] = range(1, len(gdf) + 1)
    # 估算字段（实际研究请替换为真实数据）
    gdf['population'] = np.random.randint(500, 8000, size=len(gdf))
    gdf['built_year'] = np.random.randint(1990, 2023, size=len(gdf))
    gdf['area_m2'] = np.random.uniform(3000, 80000, size=len(gdf))
    gdf['supply'] = np.random.uniform(0.5, 2.0, size=len(gdf))
    return gdf

# 加载数据（require_coords=True 表示必须先完成地理编码）
# 将 require_coords 改为 False 可使用区域中心估算进行测试
communities_gdf = load_village_data(VILLAGE_DB, require_coords=True)

if communities_gdf is not None:
    print(f"\nTotal communities: {len(communities_gdf)}")
    print("Type distribution:")
    print(communities_gdf['community_type'].value_counts())
    print(f"\n[OK] communities_gdf ready. CRS: {communities_gdf.crs}")
    print("Next: Run Cell 15+ (vulnerability profiling) then Cell 17+ (2SFCA)")
else:
    print("\n[ERROR] Failed to load village data. Check database.")
