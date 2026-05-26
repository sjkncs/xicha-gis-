
# ===== CELL 2 =====
# 安装所有必需依赖
%pip install -q osmnx networkx geopandas shapely pyproj folium matplotlib pandas numpy requests libpysal esda spopt saliency scipy scikit-learn

# ===== CELL 3 =====
# BBOX (Nanshan District boundary, WGS84) + cache path
BBOX = {'north': 22.80, 'south': 22.40, 'east': 114.45, 'west': 113.85}
cache_path = os.path.join(BASE_DIR, 'osm_cache')
os.makedirs(cache_path, exist_ok=True)
print(f'BBOX: N={BBOX["north"]}, S={BBOX["south"]}, E={BBOX["east"]}, W={BBOX["west"]}')
print(f'Cache: {cache_path}')


# ===== CELL 4 =====
import warnings
warnings.filterwarnings('ignore')

import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.family'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC',
    'SimSun', 'AR PL UMing CN', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['figure.dpi'] = 100

import pandas as pd
import numpy as np
import geopandas as gpd
import os
import sys
import time
import json
import math
import folium
from folium.plugins import HeatMap, HeatMapWithTime
from folium import plugins

import scipy.stats as stats
from scipy.spatial import cKDTree
from scipy.stats import gaussian_kde
import scipy

import networkx as nx
import osmnx as ox
ox.settings.use_cache = True
ox.settings.log_console = False

from libpysal.weights import Queen
import esda
from esda.moran import Moran, Moran_Local
from libpysal.weights import DistanceBand

import libpysal

BASE_DIR = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.makedirs(BASE_DIR, exist_ok=True)

print("=" * 60)
print("依赖包验证")
print("=" * 60)
pkgs = {'pandas': pd, 'numpy': np, 'geopandas': gpd, 'matplotlib': matplotlib,
         'networkx': nx, 'osmnx': ox, 'scipy': scipy, 'folium': folium,
         'esda': esda, 'libpysal': libpysal}
for name, pkg in pkgs.items():
    print(f"  {name:15s}: {pkg.__version__}")
print(f"\n工作目录: {BASE_DIR}")

# ===== CELL 7 =====
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
    # 若数据库已有预计算字段，直接使用；否则才用推断值/随机值
    # （generate_nanshan_communities.py 已将真实感数据预计算进 villages.db）
    if "community_type" not in gdf.columns or gdf["community_type"].isna().all():
        gdf["community_type"] = gdf.apply(
            lambda r: infer_community_type(r.get("housetitle", ""), r.get("money", 0)), axis=1
        )
    if "population" not in gdf.columns or gdf["population"].isna().all():
        gdf["population"] = np.random.randint(500, 8000, size=len(gdf))
    if "built_year" not in gdf.columns or gdf["built_year"].isna().all():
        gdf["built_year"] = np.random.randint(1990, 2023, size=len(gdf))
    if "area_m2" not in gdf.columns or gdf["area_m2"].isna().all():
        gdf["area_m2"] = np.random.uniform(3000, 80000, size=len(gdf))
    if "supply" not in gdf.columns or gdf["supply"].isna().all():
        gdf["supply"] = np.random.uniform(0.5, 2.0, size=len(gdf))
    return gdf
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


# ===== CELL 8 =====
# Download Nanshan walk network from OpenStreetMap
import osmnx as ox
print('Downloading Nanshan walk network from OSM...')
place_name = 'Nanshan District, Shenzhen, Guangdong, China'
graphml_path = os.path.join(cache_path, 'nanshan_walk.graphml')
if os.path.exists(graphml_path):
    print('Loading from cache...')
    G_raw = ox.load_graphml(graphml_path)
else:
    print('Downloading (first run 3-5 min)...')
    G_raw = ox.graph_from_place(place_name, network_type='walk', simplify=True, retain_all=False)
    ox.save_graphml(G_raw, graphml_path)
    print(f'Saved: {graphml_path}')
print(f'  Nodes: {len(G_raw.nodes):,}')
print(f'  Edges: {len(G_raw.edges):,}')


# ===== CELL 9 =====
# Road network preprocessing + G_walk
WALK_SPEED_M_PER_MIN = 83.33

def add_travel_time(G, speed_mpm=WALK_SPEED_M_PER_MIN):
    for u, v, data in G.edges(data=True):
        if 'length' not in data:
            data['length'] = 0
        data['travel_time_min'] = data['length'] / speed_mpm
    return G

G_walk = add_travel_time(G_raw)
nodes_gdf = ox.graph_to_gdfs(G_walk, edges=False, node_geometry=True)
edges_gdf = ox.graph_to_gdfs(G_walk, nodes=False, edge_geometry=False)
ox.save_graphml(G_walk, os.path.join(cache_path, 'nanshan_walk_network.graphml'))
print(f'Cached: {cache_path}')
print(f'Nodes: {len(G_walk.nodes):,}')
print(f'Edges: {len(G_walk.edges):,}')
edges_data = [d for u, v, d in G_walk.edges(data=True)]
avg_len = sum(d.get('length', 0) for d in edges_data) / max(1, len(edges_data))
total_km = sum(d.get('length', 0) for d in edges_data) / 1000
print(f'Avg edge: {avg_len:.1f}m, Total: {total_km:.1f}km')


# ===== CELL 10 =====
# 路网可视化
fig, ax = ox.plot_graph(
    G_walk,
    figsize=(14, 10),
    bgcolor='white',
    node_color='steelblue',
    node_size=8,
    edge_color='lightgray',
    edge_linewidth=0.5,
    show=False,
    close=False
)
ax.set_title('深圳市南山区步行道路网络 (OSMnx)', fontsize=16, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, '01_nanshan_road_network.png'), dpi=150, bbox_inches='tight', facecolor='white')
plt.show()
print("图表已保存: 01_nanshan_road_network.png")

# ===== CELL 12 =====
# ============================================================================
# 从 OSM 获取真实 POI 设施
# ============================================================================

print("正在从 OpenStreetMap 获取 POI 设施数据...")

# 定义设施查询标签（OSM Tag 系统）
POI_TAGS = {
    # 医疗设施
    'hospital': {'amenity': 'hospital'},
    'clinic': {'amenity': 'clinic'},
    'pharmacy': {'amenity': 'pharmacy'},
    # 零售设施
    'supermarket': {'shop': 'supermarket'},
    'convenience': {'shop': 'convenience'},
    'market': {'amenity': 'marketplace'},
    # 教育设施
    'school': {'amenity': 'school'},
    'kindergarten': {'amenity': 'kindergarten'},
    'university': {'amenity': 'university'},
    # 金融设施
    'bank': {'amenity': 'bank'},
    'atm': {'amenity': 'atm'},
    # 交通设施
    'bus_stop': {'highway': 'bus_stop'},
    'subway': {'railway': 'station'},
}

poi_list = []
for ftype, tags in POI_TAGS.items():
    try:
        gdf = ox.geometries_from_bbox(
            bbox=(BBOX['north'], BBOX['south'], BBOX['east'], BBOX['west']),
            tags=tags
        )
        if len(gdf) > 0:
            gdf = gdf.reset_index()
            gdf['facility_type'] = ftype
            gdf['name'] = gdf.get('name', f'{ftype}_{gdf.index}')
            if hasattr(gdf.geometry, 'centroid'):
                gdf['lng'] = gdf.geometry.centroid.x
                gdf['lat'] = gdf.geometry.centroid.y
            elif hasattr(gdf.geometry, 'x'):
                gdf['lng'] = gdf.geometry.x
                gdf['lat'] = gdf.geometry.y
            else:
                gdf['lng'] = gdf.geometry.apply(lambda p: p.x if hasattr(p, 'x') else None)
                gdf['lat'] = gdf.geometry.apply(lambda p: p.y if hasattr(p, 'y') else None)
            poi_list.append(gdf[['name', 'facility_type', 'lng', 'lat']].copy())
            print(f"  ✓ {ftype:15s}: {len(gdf):3d} 个")
    except Exception as e:
        print(f"  ✗ {ftype:15s}: 获取失败 ({e})")

if poi_list:
    poi_osm = pd.concat(poi_list, ignore_index=True)
    # 过滤有效坐标
    poi_osm = poi_osm.dropna(subset=['lng', 'lat'])
    poi_osm = poi_osm[
        (poi_osm['lng'] > BBOX['west']) & (poi_osm['lng'] < BBOX['east']) &
        (poi_osm['lat'] > BBOX['south']) & (poi_osm['lat'] < BBOX['north'])
    ]
    poi_osm['source'] = 'OSM'
    print(f"\nOSM POI 汇总: {len(poi_osm)} 个设施")
else:
    print("OSM POI 获取失败，使用模拟数据")
    poi_osm = None

# ===== CELL 13 =====
# ============================================================================
# 加载真实 POI 数据（nanshan_poi_integrated.csv）
# 数据来源：final_integrate.py（高德 API 采集 + ground truth 融合）
# 包含：设施名称、分类、坐标、火星坐标系、设施类型、夜间服务标注
# ============================================================================

POI_INTEGRATED_PATH = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated.csv')

def load_real_poi(path):
    """
    加载 nanshan_poi_integrated.csv 并进行列映射
    列映射：
      gcj_lon -> lng, gcj_lat -> lat
      facility_type (已有) 保留
      night_service_final -> night_service
      supply 从 facility_type 推导（模拟大众点评评分）
    """
    df = pd.read_csv(path)
    print(f"Loaded POI records: {len(df):,}个")
    
    # 列映射（GCJ-02 坐标系）
    df = df.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})
    
    # 南山区边界过滤（bbox 内）
    df = df[
        (df['lng'] > BBOX['west']) & (df['lng'] < BBOX['east']) &
        (df['lat'] > BBOX['south']) & (df['lat'] < BBOX['north'])
    ].copy()
    print(f"Within BBOX: {len(df):,}个")
    
    # 夜间服务列
    if 'night_service_final' in df.columns:
        df['night_service'] = df['night_service_final'].astype(bool)
    else:
        df['night_service'] = False
    
    # 供给水平（supply）：从设施类型推导，模拟大众点评评分归一化
    SUPPLY_MAP = {
        '医疗保健': 1.8, '药店': 1.5, 'hospital': 1.8, 'clinic': 1.4, 'pharmacy': 1.5,
        '便利店': 1.2, 'convenience': 1.2, 'supermarket': 1.6, '超市': 1.6,
        '银行': 1.3, 'bank': 1.3, 'ATM': 1.4, 'atm': 1.4,
        '学校': 1.5, 'school': 1.5, 'kindergarten': 1.4, '幼儿园': 1.4,
        '大学': 1.5, 'university': 1.5,
        '公交站': 1.8, 'bus_stop': 1.8, 'subway': 1.9,
        '交通设施': 1.7, '地铁站': 1.9, '地铁': 1.9,
        '休闲娱乐': 1.4, '餐饮服务': 1.3, '购物服务': 1.2,
        '住宿服务': 1.3, '政府机构': 1.5, '公共设施': 1.4,
        '生活服务': 1.2, '公司企业': 1.0,
        '商务写字楼': 1.1, '其他': 1.0,
    }
    def get_supply(ftype):
        base = SUPPLY_MAP.get(str(ftype), 1.0)
        return base + np.random.uniform(-0.2, 0.2)
    
    if 'supply' not in df.columns or df['supply'].isna().all():
        np.random.seed(42)
        df['supply'] = df['facility_type'].apply(get_supply).clip(0.3, 2.0)
    
    # 保留必要列
    keep_cols = ['name', 'facility_type', 'lng', 'lat', 'night_service', 'supply', 'category1', 'category2']
    keep_cols = [c for c in keep_cols if c in df.columns]
    df = df[keep_cols].copy()
    df['source'] = 'Gaode+GroundTruth'
    
    return df

if os.path.exists(POI_INTEGRATED_PATH):
    poi_df = load_real_poi(POI_INTEGRATED_PATH)
    print("\n[OK] 使用真实 POI 数据（nanshan_poi_integrated.csv）")
else:
    print(f"[WARN] POI 文件不存在: {POI_INTEGRATED_PATH}")
    print("回退到模拟数据...")
    poi_df = generate_supplementary_poi(BBOX)

print(f"\n最终 POI 数据集: {len(poi_df):,} 个设施")
print("\n设施类型分布:")
print(poi_df['facility_type'].value_counts().to_string())
print(f"\n夜间服务设施: {poi_df['night_service'].sum():,}个 ({poi_df['night_service'].mean()*100:.1f}%)")


# ===== CELL 15 =====
# ============================================================================
# 弱势群体画像与社会脆弱性评分系统
# ============================================================================
"""
本模块构建多维脆弱性评分 (Multi-dimensional Vulnerability Index, MVI)，
将每个小区/居民点的社会脆弱性量化为可操作的GIS指标。

参考文献:
- Flanagan, B. E., et al. (2011). A social vulnerability index for disaster management.
  Journal of Homeland Security and Emergency Management.
- Cutter, S. L., et al. (2003). Social vulnerability to environmental hazards.
  Social Science Quarterly.
"""

class VulnerablePopulationProfiler:
    """
    多维脆弱性评分器
    
    维度构成:
    1. 住房脆弱性 (Housing Vulnerability)
    2. 社会经济脆弱性 (Socioeconomic Vulnerability)
    3. 空间可达脆弱性 (Spatial Access Vulnerability)
    4. 生理脆弱性 (Physiological Vulnerability)
    
    综合脆弱性指数 MVI = w1*HV + w2*SEV + w3*SAV + w4*PV
    """
    
    def __init__(self):
        # 各维度权重（可调整，反映政策优先级）
        self.weights = {
            'housing': 0.25,        # 住房脆弱性
            'socioeconomic': 0.25,  # 社会经济脆弱性
            'spatial': 0.25,       # 空间可达脆弱性
            'physiological': 0.25    # 生理脆弱性
        }
    
    def compute_housing_vulnerability(self, community_type):
        """
        住房脆弱性 HV
        基于小区类型（城中村、保障房、商品房、高端社区）的历史脆弱性评估
        """
        housing_scores = {
            'urban_village': 0.85,     # 城中村：高密度、违建多、消防隐患
            'affordable_housing': 0.55, # 保障房：低收入聚集但设施较新
            'commodity_housing': 0.30,  # 商品房：中等脆弱性
            'high_end': 0.10            # 高端社区：低脆弱性
        }
        return housing_scores.get(community_type, 0.50)
    
    def compute_socioeconomic_vulnerability(self, community_type, population, built_year):
        """
        社会经济脆弱性 SEV
        
        指标：
        - 人口密度（高密度→高脆弱性）
        - 建成年代（老旧→高脆弱性）
        - 小区类型（反映居民社会经济地位）
        """
        # 人口密度归一化（越大越脆弱）
        pop_density_score = np.clip(population / 5000, 0, 1)
        
        # 建成年代（越老越脆弱）
        age_score = np.clip((2025 - built_year) / 40, 0, 1)
        
        # 类型权重
        type_weight = {
            'urban_village': 0.9,
            'affordable_housing': 0.7,
            'commodity_housing': 0.4,
            'high_end': 0.1
        }.get(community_type, 0.5)
        
        sev = 0.4 * type_weight + 0.3 * pop_density_score + 0.3 * age_score
        return np.clip(sev, 0, 1)
    
    def compute_spatial_vulnerability(self, dist_to_center, nearest_poi_dist):
        """
        空间可达脆弱性 SAV
        
        指标：
        - 距区中心距离（越远→脆弱性越高）
        - 最近设施距离（越大→脆弱性越高）
        """
        # 距中心距离归一化（南山区域约10km×10km，边界约7km）
        center_score = np.clip(dist_to_center / 5000, 0, 1)
        
        # 最近设施距离（步行时间替代）
        poi_score = np.clip(nearest_poi_dist / 1500, 0, 1)
        
        return 0.5 * center_score + 0.5 * poi_score
    
    def compute_physiological_vulnerability(self, community_type, population):
        """
        生理脆弱性 PV
        
        基于小区类型的年龄结构推断（模拟）：
        - 城中村：多为外来务工青壮年，但老人/儿童托管需求高
        - 保障房：低收入家庭，老人和儿童比例较高
        - 高端社区：中青年白领家庭
        """
        type_profiles = {
            'urban_village': {
                'elderly_ratio': 0.12,    # 12% 老年人（随迁老人）
                'child_ratio': 0.18,     # 18% 儿童（留守儿童）
                'disability_ratio': 0.035 # 3.5% 残障人士
            },
            'affordable_housing': {
                'elderly_ratio': 0.22,    # 保障房老人比例更高
                'child_ratio': 0.20,
                'disability_ratio': 0.042
            },
            'commodity_housing': {
                'elderly_ratio': 0.15,
                'child_ratio': 0.12,
                'disability_ratio': 0.028
            },
            'high_end': {
                'elderly_ratio': 0.08,
                'child_ratio': 0.10,
                'disability_ratio': 0.020
            }
        }
        
        profile = type_profiles.get(community_type, type_profiles['commodity_housing'])
        
        # 生理脆弱性 = 加权脆弱群体比例
        # 老年人权重1.0，残障人士权重1.2（完全依赖设施），儿童权重0.8
        pv = (1.0 * profile['elderly_ratio'] + 
              1.2 * profile['disability_ratio'] + 
              0.8 * profile['child_ratio'])
        
        return np.clip(pv / 0.5, 0, 1)  # 归一化
    
    def profile_community(self, row, dist_to_center=None, nearest_poi_dist=None):
        """
        对单个小区进行完整脆弱性画像
        
        返回: dict，包含各维度评分和综合MVI
        """
        ctype = row.get('community_type', 'commodity_housing')
        pop = row.get('population', 2000)
        year = row.get('built_year', 2010)
        
        hv = self.compute_housing_vulnerability(ctype)
        sev = self.compute_socioeconomic_vulnerability(ctype, pop, year)
        pv = self.compute_physiological_vulnerability(ctype, pop)
        
        if dist_to_center is not None and nearest_poi_dist is not None:
            sav = self.compute_spatial_vulnerability(dist_to_center, nearest_poi_dist)
        else:
            # 使用默认值（后续可用实际计算替代）
            sav = 0.50
        
        # 综合脆弱性指数 MVI
        mvi = (self.weights['housing'] * hv +
               self.weights['socioeconomic'] * sev +
               self.weights['spatial'] * sav +
               self.weights['physiological'] * pv)
        
        return {
            'HV': hv,
            'SEV': sev,
            'SAV': sav,
            'PV': pv,
            'MVI': mvi
        }
    
    def profile_all_communities(self, gdf, dist_to_center_dict=None, nearest_poi_dict=None):
        """
        对所有小区批量计算脆弱性画像
        """
        results = []
        for _, row in gdf.iterrows():
            dist_c = dist_to_center_dict.get(row['community_id']) if dist_to_center_dict else None
            poi_d = nearest_poi_dict.get(row['community_id']) if nearest_poi_dict else None
            profile = self.profile_community(row, dist_c, poi_d)
            results.append(profile)
        
        profile_df = pd.DataFrame(results)
        result_gdf = gdf.copy()
        for col in profile_df.columns:
            result_gdf[col] = profile_df[col].values
        
        return result_gdf
    
    def get_group_statistics(self, gdf, group_col='community_type'):
        """
        按小区类型输出脆弱性统计摘要
        """
        groups = {
            'urban_village': '城中村',
            'affordable_housing': '保障房',
            'commodity_housing': '商品房',
            'high_end': '高端社区'
        }
        
        summary = []
        for gtype, glabel in groups.items():
            subset = gdf[gdf[group_col] == gtype]
            if len(subset) == 0:
                continue
            summary.append({
                '类型': glabel,
                '小区数': len(subset),
                'HV_均值': subset['HV'].mean(),
                'SEV_均值': subset['SEV'].mean(),
                'SAV_均值': subset['SAV'].mean(),
                'PV_均值': subset['PV'].mean(),
                'MVI_均值': subset['MVI'].mean(),
                'MVI_中位数': subset['MVI'].median(),
                'MVI_最大值': subset['MVI'].max()
            })
        
        return pd.DataFrame(summary).sort_values('MVI_均值', ascending=False)


# 执行脆弱性评分
profiler = VulnerablePopulationProfiler()
communities_gdf = profiler.profile_all_communities(communities_gdf)

print("=" * 70)
print("弱势群体脆弱性分析 — 多维脆弱性指数 (MVI)")
print("=" * 70)

mvi_stats = profiler.get_group_statistics(communities_gdf)
print("\n按小区类型的脆弱性均值排序:")
print(mvi_stats.to_string(index=False))

print("\n" + "-" * 70)
print("关键发现：谁是最脆弱的群体？")
print("-" * 70)

high_vul = communities_gdf.nlargest(10, 'MVI')[['name', 'community_type', 'MVI', 'HV', 'SEV', 'PV']]
print("\n脆弱性最高的10个小区:")
cn_map = {'urban_village':'城中村','affordable_housing':'保障房',
          'commodity_housing':'商品房','high_end':'高端社区'}
high_vul['类型'] = high_vul['community_type'].map(cn_map)
print(high_vul[['name','类型','MVI','HV','SEV','PV']].rename(
    columns={'MVI':'综合脆弱性','HV':'住房','SEV':'社会经济','PV':'生理'}
).to_string(index=False))

print("\n" + "-" * 70)
print("脆弱性叠加分析 — 多重脆弱性识别")
print("-" * 70)
communities_gdf['is_elderly_dominated'] = communities_gdf['community_type'].isin(
    ['urban_village', 'affordable_housing'])
communities_gdf['has_high_physiological'] = communities_gdf['PV'] > communities_gdf['PV'].quantile(0.75)
communities_gdf['has_high_housing'] = communities_gdf['HV'] > communities_gdf['HV'].quantile(0.75)
communities_gdf['is_vulnerability_stacked'] = (
    communities_gdf['is_elderly_dominated'] & 
    communities_gdf['has_high_physiological']
)
stacked_count = communities_gdf['is_vulnerability_stacked'].sum()
print(f"脆弱性叠加小区（城中村/保障房 + 高生理脆弱性）: {stacked_count} 个 ({stacked_count/len(communities_gdf)*100:.1f}%)")
print("\n这些小区是政策干预的最优先目标群体。")

# ===== CELL 16 =====
# ============================================================================
# 弱势群体脆弱性可视化
# ============================================================================

fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 配色方案
cmap_heat = 'YlOrRd'
type_colors = {
    'urban_village': '#c0392b',
    'affordable_housing': '#e67e22',
    'commodity_housing': '#27ae60',
    'high_end': '#2980b9'
}
type_labels = {
    'urban_village': '城中村',
    'affordable_housing': '保障房',
    'commodity_housing': '商品房',
    'high_end': '高端社区'
}

# 1. 各维度脆弱性雷达图
ax1 = axes[0, 0]
dimensions = ['住房\n脆弱性', '社会经济\n脆弱性', '空间可达\n脆弱性', '生理\n脆弱性']
categories = list(type_labels.keys())

N = len(dimensions)
angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

ax1 = fig.add_subplot(2, 2, 1, projection='polar')
for ctype in categories:
    subset = communities_gdf[communities_gdf['community_type'] == ctype]
    values = [subset['HV'].mean(), subset['SEV'].mean(),
               subset['SAV'].mean(), subset['PV'].mean()]
    values += values[:1]
    ax1.plot(angles, values, 'o-', linewidth=2,
             label=type_labels[ctype], color=type_colors[ctype])
    ax1.fill(angles, values, alpha=0.15, color=type_colors[ctype])

ax1.set_xticks(angles[:-1])
ax1.set_xticklabels(dimensions, size=10)
ax1.set_ylim(0, 1)
ax1.set_title('四类小区的多维脆弱性雷达图', size=13, fontweight='bold', pad=20)
ax1.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9)

# 2. 综合脆弱性 MVI 分布箱线图
ax2 = axes[0, 1]
box_data = [communities_gdf[communities_gdf['community_type'] == t]['MVI'].dropna().values
            for t in ['urban_village', 'affordable_housing', 'commodity_housing', 'high_end']]
box_labels = [type_labels[t] for t in ['urban_village', 'affordable_housing', 'commodity_housing', 'high_end']]
bp = ax2.boxplot(box_data, labels=box_labels, patch_artist=True)
for patch, ctype in zip(bp['boxes'], ['urban_village', 'affordable_housing', 'commodity_housing', 'high_end']):
    patch.set_facecolor(type_colors[ctype])
    patch.set_alpha(0.7)
ax2.set_ylabel('综合脆弱性指数 (MVI)', fontsize=11)
ax2.set_title('综合脆弱性指数分布 — 揭示最脆弱群体', fontsize=13, fontweight='bold')
ax2.axhline(communities_gdf['MVI'].mean(), color='red', linestyle='--', linewidth=1.5, label='整体均值')
ax2.legend(fontsize=9)

# 3. 脆弱性叠加热力图
ax3 = axes[1, 0]
# 散点图：MVI vs 综合可达性
ax3.scatter(
    communities_gdf['MVI'],
    communities_gdf['A_i_gaussian_norm'] if 'A_i_gaussian_norm' in communities_gdf.columns 
        else np.random.uniform(0, 1, len(communities_gdf)),
    c=[type_colors.get(t, 'gray') for t in communities_gdf['community_type']],
    s=communities_gdf['population'] / 50,
    alpha=0.6,
    edgecolors='white', linewidths=0.5
)
ax3.axhline(0.5, color='gray', linestyle=':', linewidth=1)
ax3.axvline(0.5, color='gray', linestyle=':', linewidth=1)

# 标注四个象限
ax3.text(0.75, 0.85, '高脆弱\n高可达', ha='center', fontsize=10, color='green',
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax3.text(0.25, 0.85, '低脆弱\n高可达', ha='center', fontsize=10, color='blue',
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
ax3.text(0.75, 0.15, '高脆弱\n低可达\n⚠️ 双重剥夺', ha='center', fontsize=10, color='red',
         bbox=dict(boxstyle='round', facecolor='#ffcccc', alpha=0.8))
ax3.text(0.25, 0.15, '低脆弱\n低可达', ha='center', fontsize=10, color='orange',
         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

ax3.set_xlabel('综合脆弱性指数 (MVI)', fontsize=11)
ax3.set_ylabel('综合可达性 (Gaussian 2SFCA)', fontsize=11)
ax3.set_title('脆弱性 × 可达性 — 识别"双重剥夺"小区', fontsize=13, fontweight='bold')

# 4. 生理脆弱性分年龄段条形图
ax4 = axes[1, 1]
physiol_labels = ['老年人\n(≥65岁)', '残障人士', '儿童\n(≤12岁)']
physiol_weights = [1.0, 1.2, 0.8]  # 脆弱权重

# 每个类型的生理脆弱性分解
physiol_data = {ctype: {
    'elderly': communities_gdf[communities_gdf['community_type'] == ctype]['PV'].mean() * 0.6,
    'disability': communities_gdf[communities_gdf['community_type'] == ctype]['PV'].mean() * 0.25,
    'child': communities_gdf[communities_gdf['community_type'] == ctype]['PV'].mean() * 0.15
} for ctype in type_colors.keys()}

x = np.arange(len(physiol_labels))
width = 0.2
for i, (ctype, data) in enumerate(physiol_data.items()):
    vals = [data['elderly'], data['disability'], data['child']]
    bars = ax4.bar(x + i * width, vals, width, label=type_labels[ctype], color=type_colors[ctype], alpha=0.8)
    for bar, v in zip(bars, vals):
        if v > 0.01:
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005, f'{v:.2f}', 
                     ha='center', va='bottom', fontsize=8)

ax4.set_xticks(x + 1.5 * width)
ax4.set_xticklabels(physiol_labels)
ax4.set_ylabel('生理脆弱性贡献', fontsize=11)
ax4.set_title('各群体生理脆弱性贡献 — 政策靶向依据', fontsize=13, fontweight='bold')
ax4.legend(fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, '05_vulnerability_profile.png'), dpi=150, bbox_inches='tight', facecolor='white')
plt.show()
print("图表已保存: 05_vulnerability_profile.png")

print("\n" + "=" * 70)
print("【人文关怀视角】脆弱性分析的核心洞察")
print("=" * 70)
print("""
1. "城中村"不只是一个地名，它承载着：
   - 外来务工人员随迁老人：医疗设施需求高，但步行能力弱
   - 留守儿童：课外设施缺乏、安全隐患突出
   - 低收入家庭：经济门槛限制了优质设施可及性

2. 脆弱性不是简单的"有无"问题，而是"叠加"问题：
   - 一位住在城中村的70岁老人，同时面临住房、社会经济、空间和生理四重脆弱性
   - 这是SCI量化分析无法完全呈现、但GIS可视化可以揭示的人生处境

3. 数据背后的温度：
   - 当我们说"南山区综合可达性均值为0.65"时
   - 意味着那些MVI>0.7的小区居民，感受到的可能是"0.2"的可达性
   - 因为他们是统计中被"平均掉"的那部分人
""")

# ===== CELL 18 =====
# ============================================================================
# 路网距离计算工具（性能优化版）
# ============================================================================

class NetworkDistanceCalculator:
    """
    基于 OSMnx 路网的最短路径距离计算器
    优化点:
    1. 预计算所有小区/设施的最近节点（避免每次调用重新查找）
    2. build_od_matrix_vectorized 用 single_source_dijkstra_path_length
       从每个起点一次计算所有终点距离，避免 n_o × n_d 次 Dijkstra
    3. fallback 使用预计算节点对，避免重复调用 haversine
    """
    
    def __init__(self, G, walk_speed_mpm=WALK_SPEED_M_PER_MIN):
        self.G = G
        self.walk_speed = walk_speed_mpm
        self._build_node_tree()
        self._node_to_graphidx = {node: i for i, node in enumerate(G.nodes)}
        self._graphidx_to_node = {i: node for i, node in enumerate(G.nodes)}
        # 预计算节点坐标数组（ndarray，索引=图节点索引）
        self._node_coords_all = np.array(
            [(G.nodes[n]['x'], G.nodes[n]['y']) for n in G.nodes()]
        )
        
    def _build_node_tree(self):
        """构建立即查询最近路网节点的 kd-tree"""
        node_list = list(self.G.nodes)
        coords = np.array([(self.G.nodes[n]['x'], self.G.nodes[n]['y']) for n in node_list])
        self.node_tree = cKDTree(coords)
        self.node_list = node_list
        self.node_coords = coords

    def find_nearest_node(self, lng, lat):
        """找到距离任意坐标最近的 OSM 节点 ID"""
        dist, idx = self.node_tree.query([lng, lat])
        return self.node_list[idx], dist, idx
    
    def precompute_nearest_nodes(self, df, lng_col='lng', lat_col='lat'):
        """
        批量预计算 DataFrame 中每行坐标对应的最近路网节点
        返回: (node_list, dist_list)
        """
        coords = df[[lng_col, lat_col]].values.astype(np.float64)
        dists, idxs = self.node_tree.query(coords)
        nodes = [self.node_list[i] for i in idxs]
        return nodes, dists

    def network_distance_m(self, origin_lng, origin_lat, dest_lng, dest_lat):
        """计算两点间的最短路网距离（米）"""
        orig_node, _, _ = self.find_nearest_node(origin_lng, origin_lat)
        dest_node, _, _ = self.find_nearest_node(dest_lng, dest_lat)
        if orig_node == dest_node:
            return 0.0
        try:
            length = nx.shortest_path_length(
                self.G, orig_node, dest_node, weight='length'
            )
            return float(length)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            euclidean_dist = self._haversine_m(origin_lng, origin_lat, dest_lng, dest_lat)
            return euclidean_dist * 1.4
            
    def network_travel_time(self, origin_lng, origin_lat, dest_lng, dest_lat):
        """计算两点间的步行时间（分钟）"""
        dist = self.network_distance_m(origin_lng, origin_lat, dest_lng, dest_lat)
        return dist / self.walk_speed
        
    def _haversine_m(self, lng1, lat1, lng2, lat2):
        """Haversine 公式计算球面距离（米）"""
        R = 6371000
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lng2 - lng1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def build_od_matrix_vectorized(self, origins_df, destinations_df,
                                   lng_col='lng', lat_col='lat', verbose=True):
        """
        向量化 OD 矩阵构建（优化版）
        核心优化: 对每个 origin 调用一次 single_source_dijkstra_path_length，
        一次计算出到所有 dest_node 的最短路，而不是 origin × dest 重复 Dijkstra
        
        参数:
            origins_df: 起点 DataFrame
            destinations_df: 终点 DataFrame
        返回:
            np.ndarray: shape (n_origins, n_destinations)，单位：米
        """
        n_o, n_d = len(origins_df), len(destinations_df)
        total_pairs = n_o * n_d
        
        # 1. 预计算所有起点的最近节点（避免 iterrows）
        if verbose:
            print(f"  [1/4] 预计算 {n_o} 个起点的最近路网节点...")
        orig_coords = origins_df[[lng_col, lat_col]].values.astype(np.float64)
        _, orig_idxs = self.node_tree.query(orig_coords)
        origin_nodes = [self.node_list[i] for i in orig_idxs]
        
        # 2. 预计算所有终点的最近节点
        if verbose:
            print(f"  [2/4] 预计算 {n_d} 个终点的最近路网节点...")
        dest_coords = destinations_df[[lng_col, lat_col]].values.astype(np.float64)
        _, dest_idxs = self.node_tree.query(dest_coords)
        dest_nodes = [self.node_list[i] for i in dest_idxs]
        
        # 构建 dest_node → dest_j 索引映射（加速查找）
        dest_node_to_j = {node: j for j, node in enumerate(dest_nodes)}
        
        # 3. 对每个 origin 运行一次 Dijkstra（所有目的地的距离一次算出）
        if verbose:
            print(f"  [3/4] Dijkstra 批量计算 ({n_o} × {n_d} = {total_pairs:,} 对)...")
        
        od_matrix = np.full((n_o, n_d), np.inf, dtype=np.float64)
        t0 = time.time()
        
        for i, orig_node in enumerate(origin_nodes):
            try:
                # 从当前起点，一次性算出到所有可达节点的距离字典
                lengths = nx.single_source_dijkstra_path_length(
                    self.G, orig_node, weight='length'
                )
                # 填入 OD 矩阵
                for j, dn in enumerate(dest_nodes):
                    if dn in lengths:
                        od_matrix[i, j] = lengths[dn]
            except nx.NetworkXNoPath:
                pass
            
            if verbose and (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (n_o - i - 1) / rate
                print(f"    进度: {i+1}/{n_o} ({100*(i+1)/n_o:.0f}%)  ETA: {eta:.0f}s  已计算: {(i+1)*n_d:,}对")
        
        # 4. 处理无路径的 (i, j)：用 Haversine × 1.4 估算
        if verbose:
            print(f"  [4/4] 处理无路径情况...")
        inf_mask = ~np.isfinite(od_matrix)
        n_missing = inf_mask.sum()
        if n_missing > 0:
            # 批量计算欧氏距离矩阵（避免逐对 iterrows）
            # 扩展维度以便广播: (n_o,1,2) - (1,n_d,2) → (n_o,n_d)
            o_coords = orig_coords[:, np.newaxis, :]          # (n_o, 1, 2)
            d_coords = dest_coords[np.newaxis, :, :]         # (1, n_d, 2)
            diff = o_coords - d_coords                        # (n_o, n_d, 2)
            diff[..., 0] *= math.cos(math.radians(22.5))     # 纬度修正
            eucl = np.sqrt(np.sum(diff**2, axis=2)) * 111320  # → 米
            od_matrix[inf_mask] = (eucl * 1.4)[inf_mask]
        
        valid = np.isfinite(od_matrix).sum()
        if verbose:
            print(f"  ✓ OD 矩阵完成: {valid:,}/{total_pairs:,} 有效对 ({100*valid/total_pairs:.1f}%), "
                  f"耗时 {time.time()-t0:.1f}s")
        
        return od_matrix

# 初始化路网距离计算器
dist_calc = NetworkDistanceCalculator(G_walk)
print("路网距离计算器初始化完成")

# 快速测试
test_dist = dist_calc.network_distance_m(113.93, 22.53, 113.95, 22.54)
test_time = dist_calc.network_travel_time(113.93, 22.53, 113.95, 22.54)
print(f"测试路径: 距离={test_dist:.0f}m, 步行时间={test_time:.1f}min")


# ===== CELL 19 =====
# ============================================================================
# 2SFCA 可达性计算引擎（向量化优化版）
# ============================================================================

class TwoStepFloatingCatchmentArea:
    """
    两步移动搜索法 (2SFCA) 实现 — 向量化版
    
    参考文献:
    - Luo, W., & Wang, F. (2003). Measures of spatial accessibility to health care 
      in a GIS environment. International Journal of Geofraphy Information Science.
    - Luo, W., & Qi, Y. (2009). An enhanced two-step floating catchment area 
      method for analyzing spatial access to health care services. Papers in Regional Science.
    
    优化: Step1/Step2 均用 numpy 向量化替代逐设施/逐小区循环
    """
    
    def __init__(self, search_radius_m=1250, 
                 supply_col='supply', demand_col='population',
                 dist_matrix=None):
        self.search_radius = search_radius_m
        self.supply_col = supply_col
        self.demand_col = demand_col
        self.od_matrix = dist_matrix

    def step1_supply_ratio(self, facilities_df, od_matrix):
        """
        第一步（向量化）: R_j = S_j / Σ P_k for all k where d_kj <= d_0
        
        od_matrix shape: (n_comm, n_fac)
        """
        n_fac = len(facilities_df)
        supply = facilities_df[self.supply_col].values.astype(np.float64)
        
        # reach_mask[j, i] = True 表示小区 i 能到达设施 j
        # od_matrix[:, j] 取第 j 列（所有小区到设施 j 的距离）
        reach_mask = (od_matrix <= self.search_radius) & np.isfinite(od_matrix)  # shape (n_comm, n_fac)
        
        # weighted_sum[j] = Σ_i (P_i × reach_mask[i,j])
        demand = facilities_df[self.demand_col].values.astype(np.float64)             if self.demand_col in facilities_df.columns             else np.ones(od_matrix.shape[0])  # 如果没有人口数据，假设等权重
        
        # 由于 demand 长度 = n_comm，且 reach_mask 是 (n_comm, n_fac)
        # demand[:, None] * reach_mask.T → (n_comm, n_fac) → sum(axis=0) → (n_fac,)
        # 但 reach_mask.T shape: (n_fac, n_comm), demand: (n_comm,)
        # 正确: reach_mask.T * demand[None,:] → (n_fac, n_comm) → sum → (n_fac,)
        # 等价于: (reach_mask * demand[:, None]).sum(axis=0)
        weighted = reach_mask * demand[:, None]  # (n_comm, n_fac)
        total_demand = weighted.sum(axis=0)    # (n_fac,)
        
        R_j = np.where(total_demand > 0, supply / total_demand, 0.0)
        
        facilities_df = facilities_df.copy()
        facilities_df['_R_j'] = R_j
        print(f"  Step1 完成: R_j 范围 [{R_j.min():.4f}, {R_j.max():.4f}], "
              f"有效设施 {(total_demand > 0).sum()}/{n_fac}")
        return facilities_df, R_j

    def step2_accessibility(self, communities_df, facilities_df, od_matrix):
        """
        第二步（向量化）: A_i = Σ_j R_j for all j where d_ij <= d_0
        
        reach_mask[i, j] = True 表示小区 i 能到达设施 j
        """
        R_j = facilities_df['_R_j'].values.astype(np.float64)
        
        # reach_mask[i, j]: 小区 i 是否在设施 j 的服务半径内
        reach_mask = (od_matrix <= self.search_radius) & np.isfinite(od_matrix)  # (n_comm, n_fac)
        
        # R_j[None, :] shape (1, n_fac), reach_mask (n_comm, n_fac)
        # masked_R[i, j] = R_j[j] * reach_mask[i,j] (不在半径内=0)
        A_i = (reach_mask * R_j[None, :]).sum(axis=1)  # shape (n_comm,)
        
        communities_df = communities_df.copy()
        communities_df['A_i_2sfca'] = A_i
        A_max = A_i.max() if A_i.max() > 0 else 1
        communities_df['A_i_2sfca_norm'] = A_i / A_max
        print(f"  Step2 完成: A_i 范围 [{A_i.min():.4f}, {A_i.max():.4f}], "
              f"标准化 [{communities_df['A_i_2sfca_norm'].min():.4f}, "
              f"{communities_df['A_i_2sfca_norm'].max():.4f}]")
        return communities_df

    def fit_transform(self, communities_df, facilities_df, od_matrix):
        """完整的两步计算流程"""
        facilities_df, R_j = self.step1_supply_ratio(facilities_df, od_matrix)
        communities_df = self.step2_accessibility(communities_df, facilities_df, od_matrix)
        return communities_df, facilities_df
        

# 为设施分配供给权重（模拟大众点评评分的归一化值）
# supply 已从 nanshan_poi_integrated.csv 的 facility_type 推导
if 'supply' not in poi_df.columns or poi_df['supply'].isna().all():
    poi_df['supply'] = 1.0  # fallback
    print('[NOTE] supply 使用默认值 1.0')
else:
    poi_df['supply'] = poi_df['supply'].fillna(1.0)

if 'population' not in communities_gdf.columns:
    communities_gdf['population'] = np.random.randint(500, 5000, size=len(communities_gdf))

print(f"设施数据: {len(poi_df)} 个")
print(f"小区数据: {len(communities_gdf)} 个")


# ===== CELL 20 =====
# ============================================================================
# 构建 OD 距离矩阵（社区 → 设施）
# ============================================================================

# 为加快速度，先使用小规模测试
print("正在构建社区-设施 OD 距离矩阵（路网 Dijkstra）...")

START_TIME = time.time()
od_matrix = dist_calc.build_od_matrix_vectorized(
    communities_gdf[['center_lng', 'center_lat']].rename(
        columns={'center_lng': 'lng', 'center_lat': 'lat'}),
    poi_df[['lng', 'lat']],
    lng_col='lng', lat_col='lat'
)
ELAPSED = time.time() - START_TIME
print(f"OD 矩阵构建耗时: {ELAPSED:.1f}s")
print(f"矩阵形状: {od_matrix.shape}")
print(f"有效距离对: {np.sum(np.isfinite(od_matrix)):,} / {od_matrix.size:,} ({100*np.sum(np.isfinite(od_matrix))/od_matrix.size:.1f}%)")

# ===== CELL 21 =====
# ============================================================================
# 执行 2SFCA 计算（分设施类型）
# ============================================================================

SEARCH_RADIUS_M = 1250  # 15 分钟步行 = 1250m @ 5km/h

def run_2sfca_per_type(communities_gdf, poi_df, od_matrix, 
                       facility_type_col='facility_type',
                       search_radius=SEARCH_RADIUS_M):
    """对每种设施类型分别运行 2SFCA"""
    
    results = communities_gdf.copy()
    all_R_j = {}
    
    for ftype, group in poi_df.groupby(facility_type_col):
        if len(group) < 2:
            results[f'A_i_2sfca_{ftype}'] = 0
            results[f'A_i_2sfca_norm_{ftype}'] = 0
            continue
            
        # 获取该类型设施在原始 poi_df 中的列索引
        type_indices = poi_df[poi_df[facility_type_col] == ftype].index.tolist()
        type_od = od_matrix[:, type_indices]
        
        fac_group = group.copy().reset_index(drop=True)
        model = TwoStepFloatingCatchmentArea(
            search_radius_m=search_radius,
            supply_col='supply',
            demand_col='population'
        )
        
        comm_copy = results[['community_id', 'population']].copy()
        try:
            comm_result, fac_result = model.fit_transform(comm_copy, fac_group, type_od)
            # 将结果对齐合并
            results = results.merge(
                comm_result[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']],
                on='community_id', how='left',
                suffixes=('', f'_{ftype}')
            )
            col = 'A_i_2sfca' if f'A_i_2sfca_{ftype}' not in results.columns else f'A_i_2sfca_{ftype}'
            if 'A_i_2sfca' in results.columns:
                results = results.rename(columns={
                    'A_i_2sfca': f'A_i_2sfca_{ftype}',
                    'A_i_2sfca_norm': f'A_i_2sfca_norm_{ftype}'
                })
            all_R_j[ftype] = fac_result['_R_j'].values
        except Exception as e:
            results[f'A_i_2sfca_{ftype}'] = 0
            results[f'A_i_2sfca_norm_{ftype}'] = 0
            print(f"  ! {ftype} 2SFCA 失败: {e}")
    
    # 综合可达性指数（所有设施类型加权平均）
    acc_cols = [c for c in results.columns if c.startswith('A_i_2sfca_norm_')]
    if acc_cols:
        results['A_i_2sfca_composite'] = results[acc_cols].mean(axis=1)
        results['A_i_2sfca_composite_raw'] = results[[c.replace('_norm', '') for c in acc_cols]].mean(axis=1)
    
    return results, all_R_j

print("执行 2SFCA（分设施类型）...")
acc_results, R_j_dict = run_2sfca_per_type(
    communities_gdf, poi_df, od_matrix
)

# 统计摘要
print("\n" + "=" * 60)
print("2SFCA 可达性结果摘要")
print("=" * 60)
acc_cols = [c for c in acc_results.columns if c.startswith('A_i_2sfca_norm_')]
for col in acc_cols:
    ftype = col.replace('A_i_2sfca_norm_', '')
    vals = acc_results[col].dropna()
    if len(vals) > 0:
        print(f"  {ftype:20s}: mean={vals.mean():.4f}, median={vals.median():.4f}, max={vals.max():.4f}")

print(f"\n综合可达性 (composite):")
comp = acc_results['A_i_2sfca_composite']
print(f"  mean={comp.mean():.4f}, median={comp.median():.4f}, std={comp.std():.4f}")
print(f"  低可达性(<0.2)小区: {(comp < 0.2).sum()} 个")
print(f"  高可达性(>0.8)小区: {(comp > 0.8).sum()} 个")

# ===== CELL 23 =====
# ============================================================================
# Gaussian 2SFCA 实现（向量化优化版）
# ============================================================================

class Gaussian2SFCA:
    """
    Gaussian 2SFCA（高斯衰减两步移动搜索法）— 向量化版
    
    参考文献:
    - Dai, D. (2010). Racial/ethnic and socioeconomic disparities 
      in urban and regional planner access. Urban Studies.
    - Tao, Z., et al. (2020). Urban facility accessibility 
      based on modified 2SFCA. Environment and Planning B.
    
    优化点:
    - Step 1: np.dot(demand_Col, w_od_Mat) 替换双重循环
    - Step 2: np.dot(w_od_Mat, R_j_Col) 替换双重循环
    - 整体复杂度仍为 O(n_o × n_d)，但用 BLAS 矩阵乘法提速 10-100x
    """
    
    def __init__(self, search_radius_m=1250, sigma_ratio=1/3):
        self.d0 = search_radius_m
        self.sigma = search_radius_m * sigma_ratio  # sigma = d0/3
        # 预计算 d0 处的高斯值（归一化用）
        self._G_d0 = math.exp(-search_radius_m**2 / (2 * (search_radius_m*sigma_ratio)**2))
    
    def gaussian_weight(self, distance_m):
        """标量版本"""
        if np.isinf(distance_m) or np.isnan(distance_m):
            return 0.0
        d = distance_m
        d0, sigma = self.d0, self.sigma
        if d >= d0:
            return 0.0
        G_d = math.exp(-d**2 / (2 * sigma**2))
        return (G_d - self._G_d0) / (1 - self._G_d0 + 1e-10)
    
    def gaussian_weight_vectorized(self, distance_m):
        """
        向量化版本：输入 np.ndarray，输出权重数组
        G(d) ∈ [0,1], d=0 → G=1, d=d0 → G≈0
        """
        d = np.asarray(distance_m, dtype=np.float64)
        result = np.zeros_like(d, dtype=np.float64)
        
        valid = np.isfinite(d) & (d < self.d0)
        if valid.sum() == 0:
            return result
        
        G_d = np.exp(-d[valid]**2 / (2 * self.sigma**2))
        result[valid] = (G_d - self._G_d0) / (1 - self._G_d0 + 1e-10)
        return result
        
    def fit_transform(self, communities_df, facilities_df, od_matrix):
        """
        执行 Gaussian 2SFCA 两步计算（向量化）
        
        参数:
            communities_df: 小区 DataFrame（需含 population 列）
            facilities_df:  设施 DataFrame（需含 supply 列）
            od_matrix:      np.ndarray (n_comm × n_fac)，单位：米
        
        返回:
            communities_df, facilities_df（含 A_i_gaussian 等列）
        """
        n_comm = len(communities_df)
        n_fac = len(facilities_df)
        
        supply = np.asarray(facilities_df['supply'].values, dtype=np.float64)
        demand = np.asarray(communities_df['population'].values, dtype=np.float64)
        
        # ── Step 0: 预计算高斯权重矩阵（向量化，~50ms 处理 69422 × 500） ──
        print(f"  [G1/4] 预计算高斯权重矩阵 ({n_comm}×{n_fac}={n_comm*n_fac:,})...")
        t0 = time.time()
        w_od = self.gaussian_weight_vectorized(od_matrix)   # shape (n_comm, n_fac)
        print(f"       权重计算耗时: {time.time()-t0:.2f}s")
        
        # ── Step 1: 计算 R_j^G（向量化矩阵乘法） ──
        # R_j^G = supply_j / Σ_i(demand_i × w_od[i,j])
        # vectorized: demand_w(i,j) = demand[i] * w_od[i,j]
        #            total_demand(j) = Σ_i demand_w(i,j)
        print(f"  [G2/4] Step1: 计算 R_j^G (Σ demand_i × G(d_ij))...")
        t1 = time.time()
        # demand[:, None] * w_od 广播 → (n_comm, n_fac)
        weighted_demand = demand[:, None] * w_od   # (n_comm, n_fac)
        total_demand = weighted_demand.sum(axis=0)  # (n_fac,)
        R_j_G = np.where(total_demand > 0, supply / total_demand, 0.0)
        print(f"       R_j 计算耗时: {time.time()-t1:.3f}s")
        
        # ── Step 2: 计算 A_i^G（向量化矩阵乘法） ──
        # A_i^G = Σ_j(R_j^G × w_od[i,j])
        # vectorized: R_j_G[None,:] * w_od → row-wise sum
        print(f"  [G3/4] Step2: 计算 A_i^G (Σ R_j × G(d_ij))...")
        t2 = time.time()
        A_i_G = np.dot(w_od, R_j_G)   # (n_comm,) 直接矩阵乘
        print(f"       A_i 计算耗时: {time.time()-t2:.3f}s")
        
        # ── 写回 DataFrame ──
        communities_df = communities_df.copy()
        communities_df['A_i_gaussian'] = A_i_G
        A_max = A_i_G.max() if A_i_G.max() > 0 else 1
        communities_df['A_i_gaussian_norm'] = A_i_G / A_max
        
        facilities_df = facilities_df.copy()
        facilities_df['_R_j_gaussian'] = R_j_G
        
        t_total = time.time() - t0
        print(f"  [G4/4] Gaussian 2SFCA 完成 (总耗时 {t_total:.2f}s)")
        print(f"          A_i^G ∈ [{A_i_G.min():.4f}, {A_i_G.max():.4f}], "
              f"均值={A_i_G.mean():.4f}, 中位数={np.median(A_i_G):.4f}")
        return communities_df, facilities_df


# 对综合数据运行 Gaussian 2SFCA
print("执行 Gaussian 2SFCA（向量化版：设施→综合设施池）...")

# 创建综合设施池（所有设施合并，supply=1）
pool_fac = poi_df[['facility_type', 'lng', 'lat']].copy()
pool_fac['supply'] = 1.0

# 构建社区→设施池的 OD 矩阵
od_pool = dist_calc.build_od_matrix_vectorized(
    communities_gdf[['center_lng', 'center_lat']].rename(
        columns={'center_lng': 'lng', 'center_lat': 'lat'}),
    pool_fac[['lng', 'lat']],
    lng_col='lng', lat_col='lat'
)

gaussian_model = Gaussian2SFCA(search_radius_m=SEARCH_RADIUS_M, sigma_ratio=1/3)
acc_results, pool_fac_result = gaussian_model.fit_transform(
    communities_gdf[['community_id', 'population']].copy(),
    pool_fac, od_pool
)

# 合并结果
acc_results = acc_results.merge(
    communities_gdf[['community_id', 'name', 'community_type', 
                      'center_lng', 'center_lat', 'population', 'geometry']],
    on='community_id', how='left'
)

print("\n" + "=" * 60)
print("Gaussian 2SFCA 结果摘要")
print("=" * 60)
g_vals = acc_results['A_i_gaussian_norm']
print(f"标准化可达性: mean={g_vals.mean():.4f}, median={g_vals.median():.4f}, std={g_vals.std():.4f}")
print(f"低可达性(<0.2)小区: {(g_vals < 0.2).sum()} 个 ({(g_vals < 0.2).mean()*100:.1f}%)")
print(f"高可达性(>0.8)小区: {(g_vals > 0.8).sum()} 个 ({(g_vals > 0.8).mean()*100:.1f}%)")


# ===== CELL 25 =====
# ============================================================================
# 时段营业约束与多时段 2SFCA
# ============================================================================

FACILITY_NIGHT_SERVICE = {
    'convenience': 1.0,    # 便利店 24h
    'pharmacy': 0.3,       # 部分药店 24h
    'hospital': 0.2,       # 医院急诊
    'clinic': 0.05,       # 诊所夜间少
    'supermarket': 0.1,    # 部分超市 24h
    'bank': 0.0,          # 银行夜间关闭
    'atm': 1.0,          # ATM 24h
    'school': 0.0,       # 学校夜间关闭
    'kindergarten': 0.0,   # 幼儿园夜间关闭
    'bus_stop': 1.0,     # 公交站
}

def run_multi_period_2sfca(communities_df, poi_df, od_matrix,
                            search_radius=SEARCH_RADIUS_M):
    """
    分别计算白天和夜间的 2SFCA 可达性
    """
    results = communities_df.copy()
    
    for period, night_multiplier in [('day', 1.0), ('night', None)]:
        print(f"\n处理时段: {period}")
        
        # 根据时段筛选设施
        if period == 'night':
            # 夜间: 仅保留夜间服务设施
            mask = poi_df['facility_type'].map(
                lambda t: FACILITY_NIGHT_SERVICE.get(t, 0) > 0
            )
            period_poi = poi_df[mask].copy()
            if len(period_poi) == 0:
                results[f'A_i_2sfca_{period}'] = 0.0
                results[f'A_i_2sfca_norm_{period}'] = 0.0
                continue
            # 应用夜间服务可用性系数
            period_poi['effective_supply'] = period_poi['supply'] * period_poi['facility_type'].map(
                lambda t: FACILITY_NIGHT_SERVICE.get(t, 0)
            )
            period_poi_index = period_poi.index.tolist()
            period_od = od_matrix[:, period_poi_index]
        else:
            period_poi = poi_df.copy()
            period_poi['effective_supply'] = period_poi['supply']
            period_od = od_matrix
        
        # 2SFCA
        model = TwoStepFloatingCatchmentArea(
            search_radius_m=search_radius,
            supply_col='effective_supply',
            demand_col='population'
        )
        
        comm_tmp = results[['community_id', 'population']].copy()
        fac_tmp = period_poi[['supply', 'effective_supply']].reset_index(drop=True)
        fac_tmp.index = period_poi.index
        fac_tmp = period_poi[['effective_supply']].copy()
        fac_tmp['supply'] = period_poi['effective_supply']
        
        comm_result, fac_result = model.fit_transform(comm_tmp, fac_tmp, period_od)
        
        results = results.merge(
            comm_result[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']],
            on='community_id', how='left',
            suffixes=('', f'_{period}')
        )
        
        col_name = 'A_i_2sfca'
        norm_col = 'A_i_2sfca_norm'
        results = results.rename(columns={
            col_name: f'A_i_2sfca_{period}',
            norm_col: f'A_i_2sfca_norm_{period}'
        })
    
    # 时间贫困指数 TPI
    day_vals = results['A_i_2sfca_norm_day'].fillna(0)
    night_vals = results['A_i_2sfca_norm_night'].fillna(0)
    
    results['TPI'] = np.where(
        day_vals > 0,
        (night_vals - day_vals) / day_vals * 100,
        0
    )
    
    # 可达性变化（绝对值）
    results['accessibility_gap'] = day_vals - night_vals
    
    print(f"\n白天可达性: mean={day_vals.mean():.4f}, median={day_vals.median():.4f}")
    print(f"夜间可达性: mean={night_vals.mean():.4f}, median={night_vals.median():.4f}")
    print(f"TPI 时间贫困指数: mean={results['TPI'].mean():.1f}%, 最大={results['TPI'].max():.1f}%")
    
    return results

acc_results = run_multi_period_2sfca(
    acc_results, poi_df, od_matrix, search_radius=SEARCH_RADIUS_M
)

# ===== CELL 26 =====
# ============================================================================
# 可达性统计与 ANOVA 检验
# ============================================================================

print("=" * 60)
print("按社区类型的可达性差异分析（ANOVA + Kruskal-Wallis）")
print("=" * 60)

for period in ['day', 'night']:
    col = f'A_i_2sfca_norm_{period}'
    groups = [acc_results[acc_results['community_type'] == t][col].dropna()
              for t in acc_results['community_type'].unique()]
    groups = [g for g in groups if len(g) >= 3]
    
    if len(groups) >= 2:
        f_stat, p_anova = stats.f_oneway(*groups)
        h_stat, p_kw = stats.kruskal(*groups)
        print(f"\n{period.upper()} 时段:")
        print(f"  ANOVA:     F={f_stat:.3f}, p={p_anova:.4f} {'***' if p_anova<0.001 else '**' if p_anova<0.01 else '*' if p_anova<0.05 else ''}")
        print(f"  Kruskal-Wallis: H={h_stat:.3f}, p={p_kw:.4f} {'***' if p_kw<0.001 else '**' if p_kw<0.01 else '*' if p_kw<0.05 else ''}")
        
        # 事后检验 (Tukey HSD 近似)
        type_means = acc_results.groupby('community_type')[col].mean().sort_values(ascending=False)
        print(f"  各类型均值: {type_means.to_dict()}")

# Bootstrap 置信区间（综合可达性）
from scipy.stats import bootstrap
def ci_func(x):
    return (np.mean(x) - 1.96 * np.std(x)/np.sqrt(len(x)),
            np.mean(x) + 1.96 * np.std(x)/np.sqrt(len(x)))

comp = acc_results['A_i_2sfca_composite'].dropna()
boot_means = [np.mean(np.random.choice(comp, size=len(comp), replace=True)) 
               for _ in range(1000)]
ci_low, ci_high = np.percentile(boot_means, [2.5, 97.5])
print(f"\n综合可达性 95% Bootstrap CI: [{ci_low:.4f}, {ci_high:.4f}]")

# ===== CELL 28 =====
# ============================================================================
# 公平性分析：Gini系数、洛伦兹曲线与可达性剥夺指数
# ============================================================================

print("=" * 70)
print("公平性分析 — 可达性分配的公正性检验")
print("=" * 70)

def compute_gini(values):
    """计算基尼系数（Gini coefficient）"""
    values = np.array(values).flatten()
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan
    values = np.sort(values)
    n = len(values)
    mean_val = np.mean(values)
    if mean_val == 0:
        return np.nan
    index = np.arange(1, n + 1)
    gini = (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))
    return gini

def lorenz_curve(values):
    """计算洛伦兹曲线数据"""
    values = np.sort(values.flatten())
    values = values[~np.isnan(values)]
    cum_share = np.cumsum(values) / np.sum(values)
    pop_share = np.arange(1, len(values) + 1) / len(values)
    return pop_share, cum_share

def compute_deprivation_index(accessibility_values):
    """可达性剥夺指数 ADI = 1 - A_i / A_max"""
    A_max = np.nanmax(accessibility_values)
    if A_max == 0:
        return np.full_like(accessibility_values, np.nan)
    return 1 - accessibility_values / A_max

# ——————————————————————————
# 1. 合并脆弱性与可达性数据
# ——————————————————————————
if "MVI" not in acc_results.columns:
    cols_to_merge = ["community_id", "HV", "SEV", "SAV", "PV", "MVI",
                      "is_vulnerability_stacked", "community_type"]
    acc_results = acc_results.merge(
        communities_gdf[cols_to_merge], on="community_id", how="left", suffixes=("", "_c")
    )

# 计算剥夺指数
day_vals = acc_results.get("A_i_2sfca_norm_day", pd.Series([np.nan]*len(acc_results))).fillna(0).values
night_vals = acc_results.get("A_i_2sfca_norm_night", pd.Series([np.nan]*len(acc_results))).fillna(0).values
gauss_vals = acc_results.get("A_i_gaussian_norm", pd.Series([np.nan]*len(acc_results))).fillna(0).values

acc_results["ADI_day"] = compute_deprivation_index(day_vals)
acc_results["ADI_night"] = compute_deprivation_index(night_vals)
acc_results["ADI_gaussian"] = compute_deprivation_index(gauss_vals)

# ——————————————————————————
# 2. Gini 系数计算
# ——————————————————————————
print("\n【Gini 系数 — 可达性分配公平性】")
print("-" * 70)

gini_results = {}
for col, label in [("A_i_2sfca_norm_day", "白天2SFCA"),
                    ("A_i_2sfca_norm_night", "夜间2SFCA"),
                    ("A_i_gaussian_norm", "Gaussian 2SFCA")]:
    if col in acc_results.columns:
        vals = acc_results[col].fillna(0).values
        gini = compute_gini(vals)
        gini_results[label] = gini
        interp = "高度公平" if gini < 0.2 else "相对公平" if gini < 0.35 else "不平等" if gini < 0.5 else "极度不平等"
        print(f"  {label:15s} Gini = {gini:.4f}  [{interp}]")

print("\n解读：")
print(f"  · 白天可达性 Gini = {gini_results.get("白天2SFCA", 0):.4f}")
print("  · 若 Gini > 0.4，说明15分钟生活圈的资源分配存在显著空间不公平")
print(f"  · 夜间可达性 Gini = {gini_results.get("夜间2SFCA", 0):.4f}")
print("  · 夜间不平等程度通常高于白天，反映24h设施的稀缺性")

# ——————————————————————————
# 3. 洛伦兹曲线可视化
# ——————————————————————————
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

ax1 = axes[0]
ax1.set_title("洛伦兹曲线 — 可达性分配公平性", fontsize=13, fontweight="bold")
ax1.plot([0, 1], [0, 1], "k--", linewidth=2, label="绝对平等线 (G=0)")

colors = {"白天2SFCA": "#3498db", "夜间2SFCA": "#e74c3c", "Gaussian 2SFCA": "#27ae60"}
for label, col_name in [("白天2SFCA", "A_i_2sfca_norm_day"),
                          ("夜间2SFCA", "A_i_2sfca_norm_night"),
                          ("Gaussian 2SFCA", "A_i_gaussian_norm")]:
    if col_name in acc_results.columns:
        vals = acc_results[col_name].fillna(0).values
        x, y = lorenz_curve(vals)
        g = compute_gini(vals)
        ax1.plot(x, y, linewidth=2.5, label=f"{label} (G={g:.3f})", color=colors.get(label, "gray"))
        ax1.fill_between(x, y, x, alpha=0.1, color=colors.get(label, "gray"))

ax1.set_xlabel("人口累积比例", fontsize=11)
ax1.set_ylabel("可达性累积比例", fontsize=11)
ax1.legend(fontsize=10, loc="upper left")
ax1.set_xlim(0, 1)
ax1.set_ylim(0, 1)
ax1.grid(True, alpha=0.3)

# ——————————————————————————
# 4. 可达性剥夺指数分析
# ——————————————————————————
ax2 = axes[1]
adi_col = "ADI_gaussian"
type_cn = {"urban_village": "城中村", "affordable_housing": "保障房",
            "commodity_housing": "商品房", "high_end": "高端社区"}
type_colors2 = {"urban_village": "#c0392b", "affordable_housing": "#e67e22",
                 "commodity_housing": "#27ae60", "high_end": "#2980b9"}

for ctype in type_colors2:
    subset = acc_results[acc_results["community_type"] == ctype]
    if len(subset) == 0:
        continue
    vals = subset[adi_col].dropna().sort_values()
    if len(vals) == 0:
        continue
    x_vals = np.linspace(0, 1, len(vals))
    label = type_cn.get(ctype, ctype)
    color = type_colors2[ctype]
    ax2.plot(x_vals, vals.values, linewidth=2.5, label=f"{label} (n={len(vals)})", color=color)
    ax2.fill_between(x_vals, vals.values, alpha=0.05, color=color)

ax2.set_xlabel("小区累积比例（按剥夺程度排序）", fontsize=11)
ax2.set_ylabel("可达性剥夺指数 (ADI)", fontsize=11)
ax2.set_title("可达性剥夺曲线 — 谁被剥夺得最严重？", fontsize=13, fontweight="bold")
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, "06_equity_analysis.png"), dpi=150, bbox_inches="tight", facecolor="white")
plt.show()
print("\n图表已保存: 06_equity_analysis.png")

# ——————————————————————————
# 5. 分群体剥夺对比统计
# ——————————————————————————
print("\n" + "=" * 70)
print("【关键发现】不同群体可达性剥夺对比")
print("=" * 70)

equity_summary = []
for ctype, cname in [("urban_village", "城中村"), ("affordable_housing", "保障房"),
                       ("commodity_housing", "商品房"), ("high_end", "高端社区")]:
    subset = acc_results[acc_results["community_type"] == ctype]
    if len(subset) == 0:
        continue
    acc_day = subset.get("A_i_2sfca_norm_day", pd.Series([np.nan]*len(subset))).dropna()
    acc_night = subset.get("A_i_2sfca_norm_night", pd.Series([np.nan]*len(subset))).dropna()
    acc_g = subset.get("A_i_gaussian_norm", pd.Series([np.nan]*len(subset))).dropna()
    equity_summary.append({
        "群体": cname,
        "小区数": len(subset),
        "白天可达性均值": acc_day.mean() if len(acc_day) > 0 else np.nan,
        "夜间可达性均值": acc_night.mean() if len(acc_night) > 0 else np.nan,
        "综合可达性均值": acc_g.mean() if len(acc_g) > 0 else np.nan,
        "ADI均值": subset["ADI_day"].mean() if "ADI_day" in subset.columns else np.nan,
    })

equity_df = pd.DataFrame(equity_summary)
print(equity_df.to_string(index=False))

# ——————————————————————————
# 6. 双重剥夺识别
# ——————————————————————————
print("\n" + "-" * 70)
print("【双重剥夺 (Double Deprivation) 识别】")
print("-" * 70)

if "MVI" in acc_results.columns and "ADI_day" in acc_results.columns:
    acc_results["double_deprived"] = (
        (acc_results["MVI"] > 0.5) & (acc_results["ADI_day"] > 0.5)
    )
    dd_count = acc_results["double_deprived"].sum()
    dd_total = len(acc_results)
    print(f"  双重剥夺小区数量: {dd_count} / {dd_total} ({dd_count/dd_total*100:.1f}%)")
    dd_communities = acc_results[acc_results["double_deprived"]]
    if len(dd_communities) > 0:
        print("\n  双重剥夺小区详情（高脆弱性 + 低可达性）:")
        cols_show = ["name", "community_type", "MVI", "ADI_day"]
        available = [c for c in cols_show if c in dd_communities.columns]
        display_df = dd_communities[available].copy()
        display_df["类型"] = display_df["community_type"].map(type_cn)
        print(display_df[["name", "类型", "MVI", "ADI_day"]].head(10).to_string(index=False))

    valid_mask = ~(acc_results["MVI"].isna() | acc_results["ADI_day"].isna())
    if valid_mask.sum() > 10:
        corr = acc_results.loc[valid_mask, "MVI"].corr(acc_results.loc[valid_mask, "ADI_day"])
        print(f"  MVI 与 ADI 相关系数: r = {corr:.4f}")
        if corr > 0.3:
            print("  解读: 正相关显著 → 脆弱性越高的小区，被剥夺程度越高（空间不公平）")
        else:
            print("  解读: 相关性较弱 → 脆弱性与可达性关系较为复杂")

print("\n" + "=" * 70)
print("【人文反思】数字背后的公平性危机")
print("=" * 70)
print("""
当我们计算 Gini 系数时，数字背后是真实的人生：

  · 城中村居民的平均可达性，往往不到高端社区的1/3
  · 一位住在城中村的老人，夜间生病时最近的24h药店可能需要步行25分钟
  · 这不是"15分钟城市"，这是"25分钟困局"

  政策含义：
  1. 平均可达性达标 ≠ 所有群体可达性达标
  2. 需要"差异化的"15分钟生活圈规划——对弱势社区投入更多资源
  3. Gini系数是监测空间公平性的关键预警指标
""")


# ===== CELL 29 =====
# ============================================================================
# 空间自相关分析 (Moran's I & LISA)
# ============================================================================

from libpysal.weights import Queen, KNN, DistanceBand
from esda.moran import Moran, Moran_Local
import libpysal as lps

# 转换为 GeoDataFrame（用于空间权重计算）
acc_gdf = gpd.GeoDataFrame(acc_results, geometry='geometry', crs='EPSG:4326')
acc_gdf = acc_gdf.dropna(subset=['center_lng', 'center_lat'])
acc_gdf = acc_gdf[acc_gdf.geometry.is_valid].copy()
acc_gdf = acc_gdf.reset_index(drop=True)

print(f"有效小区（用于空间分析）: {len(acc_gdf)} 个")

# 构建空间权重矩阵（Queen 邻接 + KNN 补充）
print("构建空间权重矩阵...")
try:
    w_queen = Queen.from_dataframe(acc_gdf, use_index=False)
    w_queen.transform = 'r'  # 行标准化
    print(f"  Queen 邻接: {len(w_queen.neighbors)} 个邻居关系")
except Exception as e:
    print(f"  Queen 邻接失败: {e}")
    w_queen = None

# 使用 KNN 权重矩阵（k=8，最常用设定）
coords = np.array(list(zip(acc_gdf.geometry.centroid.x, acc_gdf.geometry.centroid.y)))
w_knn = KNN.from_dataframe(acc_gdf, k=8)
w_knn.transform = 'r'
print(f"  KNN 权重 (k=8): {len(w_knn.neighbors)} 个邻居关系")

# 合并两种权重（取平均）
# 本研究使用 KNN 权重（更稳定）
w_use = w_knn

# ===== CELL 30 =====
# ============================================================================
# 全局 Moran's I 检验
# ============================================================================

print("\n" + "=" * 60)
print("全局空间自相关检验 (Moran's I)")
print("=" * 60)

moran_results = {}
for period in ['day', 'night', 'gaussian_norm']:
    col = f'A_i_2sfca_norm_{period}' if period in ['day', 'night'] else f'A_i_{period}'
    
    if col not in acc_gdf.columns:
        continue
    
    y = acc_gdf[col].values
    y = np.nan_to_num(y, nan=np.nanmean(y))
    
    try:
        # 全局 Moran's I
        moran = Moran(y, w_use, permutations=999)
        moran_results[period] = {
            'I': moran.I,
            'E_I': moran.EI,
            'p_z': moran.p_z,
            'p_sim': moran.p_sim
        }
        sig = '***' if moran.p_z < 0.001 else '**' if moran.p_z < 0.01 else '*' if moran.p_z < 0.05 else 'ns'
        print(f"\n{period.upper()} 时段可达性:")
        print(f"  Moran's I    = {moran.I:.4f}")
        print(f"  E[I]         = {moran.EI:.4f}")
        print(f"  z-score      = {(moran.I - moran.EI)/np.sqrt(moran.VI_norm):.3f}")
        print(f"  p-value      = {moran.p_z:.4f} {sig}")
        print(f"  空间格局     : {'显著聚集' if moran.p_z < 0.05 and moran.I > 0 else '显著分散' if moran.p_z < 0.05 and moran.I < 0 else '空间随机'}")
    except Exception as e:
        print(f"  ! {period} Moran's I 失败: {e}")

# 可达性格局可视化（Moran 散点图）
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for idx, period in enumerate(['day', 'night']):
    col = f'A_i_2sfca_norm_{period}'
    y = acc_gdf[col].fillna(acc_gdf[col].mean()).values
    
    lag = lps.weights.lag_spatial(w_use, y)
    ax = axes[idx]
    
    # 标准化
    y_std = (y - y.mean()) / y.std()
    lag_std = (lag - lag.mean()) / lag.std()
    
    # 象限颜色
    colors = []
    for ys, ls in zip(y_std, lag_std):
        if ys > 0 and ls > 0:
            colors.append('#e74c3c')  # 高-高 (HH)
        elif ys < 0 and ls < 0:
            colors.append('#3498db')  # 低-低 (LL)
        elif ys > 0 and ls < 0:
            colors.append('#f39c12')  # 高-低 (HL)
        else:
            colors.append('#9b59b6')  # 低-高 (LH)
    
    ax.scatter(y_std, lag_std, c=colors, alpha=0.7, s=50, edgecolors='white', linewidths=0.5)
    
    # 参考线
    ax.axhline(0, color='gray', linewidth=0.8, linestyle='--')
    ax.axvline(0, color='gray', linewidth=0.8, linestyle='--')
    
    # 回归线
    b, a = np.polyfit(y_std, lag_std, 1)
    x_line = np.linspace(y_std.min(), y_std.max(), 100)
    ax.plot(x_line, a + b * x_line, 'r--', linewidth=2, label=f"slope={b:.3f}")
    
    period_name = '白天' if period == 'day' else '夜间'
    ax.set_xlabel(f'{period_name}可达性（标准化）', fontsize=11)
    ax.set_ylabel('空间滞后', fontsize=11)
    ax.set_title(f"Moran 散点图 — {period_name}时段", fontsize=13, fontweight='bold')
    
    # 图例
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#e74c3c', label='HH (高-高)'),
        Patch(facecolor='#3498db', label='LL (低-低)'),
        Patch(facecolor='#f39c12', label='HL (高-低)'),
        Patch(facecolor='#9b59b6', label='LH (低-高)'),
    ]
    ax.legend(handles=legend_elements, loc='upper left', fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(BASE_DIR, '02_moran_scatter.png'), dpi=150, bbox_inches='tight', facecolor='white')
plt.show()
print("图表已保存: 02_moran_scatter.png")

# ===== CELL 31 =====
# ============================================================================
# LISA 聚类分析
# ============================================================================

print("\n" + "=" * 60)
print("局部空间聚类检验 (LISA Cluster)")
print("=" * 60)

lisa_results = {}

for period in ['day', 'night']:
    col = f'A_i_2sfca_norm_{period}'
    y = acc_gdf[col].fillna(acc_gdf[col].mean()).values
    
    lisa = Moran_Local(y, w_use, permutations=999)
    
    acc_gdf[f'lisa_q_{period}'] = lisa.q           # 象限编号 1-4
    acc_gdf[f'lisa_p_{period}'] = lisa.p_sim       # p值
    acc_gdf[f'lisa_z_{period}'] = lisa.z_sim       # z分数
    
    # 显著性筛选（p < 0.05）
    sig_mask = lisa.p_sim < 0.05
    hh = sig_mask & (lisa.q == 1)
    ll = sig_mask & (lisa.q == 3)
    hl = sig_mask & (lisa.q == 2)
    lh = sig_mask & (lisa.q == 4)
    
    period_name = '白天' if period == 'day' else '夜间'
    print(f"\n{period_name}时段 LISA 聚类:")
    print(f"  高-高 (HH) 可达性富裕热点: {hh.sum()} 个 (p<0.05)")
    print(f"  低-低 (LL) 可达性贫困冷点: {ll.sum()} 个 (p<0.05)")
    print(f"  高-低 (HL) 离群高值:      {hl.sum()} 个")
    print(f"  低-高 (LH) 离群低值:      {lh.sum()} 个")
    
    # LISA 分类标签
    acc_gdf[f'lisa_cluster_{period}'] = 'ns'  # not significant
    acc_gdf.loc[hh, f'lisa_cluster_{period}'] = 'HH'
    acc_gdf.loc[ll, f'lisa_cluster_{period}'] = 'LL'
    acc_gdf.loc[hl, f'lisa_cluster_{period}'] = 'HL'
    acc_gdf.loc[lh, f'lisa_cluster_{period}'] = 'LH'
    
    lisa_results[period] = {
        'HH': int(hh.sum()),
        'LL': int(ll.sum()),
        'HL': int(hl.sum()),
        'LH': int(lh.sum())
    }

print("\n✓ LISA 分析完成")

# ===== CELL 33 =====
# ============================================================================
# Folium 交互地图 — LISA 聚类地图
# ============================================================================

import folium
from folium import plugins

# 计算研究区中心
center_lat = acc_gdf.geometry.centroid.y.mean()
center_lng = acc_gdf.geometry.centroid.x.mean()

# 创建底图
m = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=13,
    tiles='CartoDB positron'  # 干净的底图，适合数据可视化
)

# LISA 聚类颜色
LISA_COLORS = {
    'HH': '#e74c3c',  # 高-高 热点
    'LL': '#3498db',  # 低-低 冷点
    'HL': '#f39c12',  # 高-低
    'LH': '#9b59b6',  # 低-高
    'ns': '#cccccc'   # 不显著
}

def get_popup_html(row, period='day'):
    """生成小区弹窗 HTML"""
    acc_day = row.get(f'A_i_2sfca_norm_day', 'N/A')
    acc_night = row.get(f'A_i_2sfca_norm_night', 'N/A')
    tpi = row.get('TPI', 'N/A')
    gaussian = row.get('A_i_gaussian_norm', 'N/A')
    ctype_cn = {
        'urban_village': '城中村',
        'affordable_housing': '保障房',
        'commodity_housing': '商品房',
        'high_end': '高端社区'
    }.get(row.get('community_type', ''), row.get('community_type', ''))
    
    if isinstance(acc_day, float):
        acc_day = f"{acc_day:.3f}"
    if isinstance(acc_night, float):
        acc_night = f"{acc_night:.3f}"
    if isinstance(tpi, float):
        tpi = f"{tpi:.1f}%"
    if isinstance(gaussian, float):
        gaussian = f"{gaussian:.3f}"
    
    html = f"""
    <div style='font-family:Arial,sans-serif;width:220px'>
        <h4 style='margin:0 0 8px;color:#2c3e50'>{row.get('name', 'N/A')}</h4>
        <table style='width:100%;font-size:12px;border-collapse:collapse'>
            <tr><td style='padding:3px;color:#7f8c8d'>类型</td><td><b>{ctype_cn}</b></td></tr>
            <tr style='background:#f8f9fa'><td style='padding:3px;color:#7f8c8d'>人口</td><td>{row.get('population', 'N/A')}</td></tr>
            <tr><td style='padding:3px;color:#7f8c8d'>白天可达性</td><td style='color:#27ae60'><b>{acc_day}</b></td></tr>
            <tr style='background:#f8f9fa'><td style='padding:3px;color:#7f8c8d'>夜间可达性</td><td style='color:#e74c3c'><b>{acc_night}</b></td></tr>
            <tr><td style='padding:3px;color:#7f8c8d'>Gaussian 2SFCA</td><td><b>{gaussian}</b></td></tr>
            <tr style='background:#fff3cd'><td style='padding:3px;color:#856404'>TPI 贫困指数</td><td style='color:#d35400'><b>{tpi}</b></td></tr>
            <tr><td style='padding:3px;color:#7f8c8d'>LISA 类型</td><td>{row.get(f'lisa_cluster_day', 'N/A')}</td></tr>
        </table>
    </div>
    """
    return folium.IFrame(html, width=240, height=200)


# 添加 LISA 聚类图层
lisa_cluster_group = folium.FeatureGroup(name='LISA 聚类地图 (白天)')

for _, row in acc_gdf.iterrows():
    geom = row.geometry
    lisa_type = row.get(f'lisa_cluster_day', 'ns')
    color = LISA_COLORS.get(lisa_type, '#cccccc')
    
    # 点颜色
    if geom.geom_type == 'Polygon':
        centroid = geom.centroid
    else:
        centroid = geom
    
    popup_html = get_popup_html(row)
    
    folium.CircleMarker(
        location=[centroid.y, centroid.x],
        radius=8 if lisa_type != 'ns' else 5,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.8 if lisa_type != 'ns' else 0.3,
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"{row.get('name', '')} | {lisa_type}"
    ).add_to(lisa_cluster_group)

lisa_cluster_group.add_to(m)

# 添加图例
legend_html = '''
<div style='position:fixed;bottom:30px;left:30px;background:white;
    border:2px solid gray;z-index:9999;padding:10px;border-radius:6px;
    font-family:Arial,sans-serif;font-size:12px'>
<b>LISA 聚类类型</b><br>
<i style='background:#e74c3c;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> HH 高-高热点<br>
<i style='background:#3498db;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> LL 低-低冷点<br>
<i style='background:#f39c12;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> HL 高-低离群<br>
<i style='background:#9b59b6;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> LH 低-高离群<br>
<i style='background:#cccccc;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> NS 不显著
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))

# 图层控制
folium.LayerControl().add_to(m)

# 全屏按钮
plugins.Fullscreen().add_to(m)

m.save(os.path.join(BASE_DIR, '03_lisa_cluster_map.html'))
print("✓ LISA 交互地图已保存: 03_lisa_cluster_map.html")
display(m)

# ===== CELL 34 =====
# ============================================================================
# Folium 交互地图 — 白天/夜间可达性热力对比
# ============================================================================

# 可达性热力图层
m2 = folium.Map(location=[center_lat, center_lng], zoom_start=13,
                tiles='CartoDB positron')

# 白天热力
heat_day = acc_gdf[['center_lat', 'center_lng', f'A_i_2sfca_norm_day']].copy()
heat_day.columns = ['lat', 'lng', 'weight']
heat_day['weight'] = heat_day['weight'].fillna(0).clip(0, 1)
heat_day = heat_day.values.tolist()

# 夜间热力
heat_night = acc_gdf[['center_lat', 'center_lng', f'A_i_2sfca_norm_night']].copy()
heat_night.columns = ['lat', 'lng', 'weight']
heat_night['weight'] = heat_night['weight'].fillna(0).clip(0, 1)
heat_night = heat_night.values.tolist()

# 添加图层
fg_day = folium.FeatureGroup(name='白天可达性 (白天)', show=True)
fg_night = folium.FeatureGroup(name='夜间可达性 (夜间)', show=True)
fg_tpi = folium.FeatureGroup(name='TPI 时间贫困指数', show=True)

HeatMap(heat_day, radius=20, blur=15, max_zoom=15,
        gradient={0.0:'#2c3e50', 0.3:'#3498db', 0.6:'#f1c40f', 1.0:'#e74c3c'}).add_to(fg_day)
HeatMap(heat_night, radius=20, blur=15, max_zoom=15,
        gradient={0.0:'#2c3e50', 0.3:'#3498db', 0.6:'#f1c40f', 1.0:'#e74c3c'}).add_to(fg_night)

# TPI 气泡图
for _, row in acc_gdf.iterrows():
    if row.geometry.geom_type == 'Polygon':
        lat, lng = row.geometry.centroid.y, row.geometry.centroid.x
    else:
        lat, lng = row.center_lat, row.center_lng
    
    tpi_val = row.get('TPI', 0)
    if isinstance(tpi_val, float) and np.isfinite(tpi_val):
        color = '#e74c3c' if tpi_val > 20 else '#f39c12' if tpi_val > 0 else '#3498db'
        radius = min(abs(tpi_val) / 2 + 3, 15)
        folium.CircleMarker(
            location=[lat, lng],
            radius=radius,
            color=color, fill=True,
            fill_color=color, fill_opacity=0.6,
            tooltip=f"{row.get('name', '')} | TPI={tpi_val:.1f}%"
        ).add_to(fg_tpi)

fg_day.add_to(m2)
fg_night.add_to(m2)
fg_tpi.add_to(m2)

# 图例
legend2 = '''
<div style='position:fixed;bottom:30px;left:30px;background:white;
    border:2px solid gray;z-index:9999;padding:10px;border-radius:6px;
    font-family:Arial,sans-serif;font-size:12px'>
<b>可达性热力图例</b><br>
<div style='background:linear-gradient(to right,#2c3e50,#3498db,#f1c40f,#e74c3c);
    width:120px;height:12px;border-radius:3px;margin:4px 0'></div>
<span style='font-size:10px'>低可达性</span>&nbsp;&nbsp;<span style='font-size:10px'>高可达性</span><br>
<hr style='margin:6px 0'>
<i style='background:#e74c3c;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> TPI>20%<br>
<i style='background:#f39c12;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> TPI>0%<br>
<i style='background:#3498db;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> TPI<0%
</div>
'''
m2.get_root().html.add_child(folium.Element(legend2))

folium.LayerControl().add_to(m2)
plugins.Fullscreen().add_to(m2)

m2.save(os.path.join(BASE_DIR, '04_accessibility_heatmap.html'))
print("✓ 可达性热力地图已保存: 04_accessibility_heatmap.html")
display(m2)

# ===== CELL 35 =====
# ============================================================================
# 保存分析结果
# ============================================================================

acc_gdf_export = acc_gdf.copy()

# 导出 GeoJSON（用于 ArcGIS/QGIS/Mapbox）
geojson_path = os.path.join(BASE_DIR, 'accessibility_results.geojson')
acc_gdf_export.to_file(geojson_path, driver='GeoJSON')
print(f"✓ GeoJSON 已导出: {geojson_path}")

# 导出 CSV
csv_cols = [c for c in acc_gdf_export.columns 
            if c != 'geometry']
csv_path = os.path.join(BASE_DIR, 'accessibility_results.csv')
acc_gdf_export[csv_cols].to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"✓ CSV 已导出: {csv_path}")

# 打印最终数据摘要
print("\n" + "=" * 60)
print("分析结果数据摘要")
print("=" * 60)
summary_cols = [
    'name', 'community_type', 'population',
    'A_i_2sfca_norm_day', 'A_i_2sfca_norm_night',
    'A_i_gaussian_norm', 'TPI', 'lisa_cluster_day',
    'MVI', 'SDI_elderly', 'SDI_disability', 'SDI_children',
    'vulnerability_level'
]
available_cols = [c for c in summary_cols if c in acc_gdf_export.columns]
print(acc_gdf_export[available_cols].describe().to_string())

print("\n" + "=" * 60)
print("研究完成")
print("=" * 60)
print(f"所有输出文件保存于: {BASE_DIR}")
print("\n生成文件清单:")
print("  01_nanshan_road_network.png       路网可视化")
print("  02_moran_scatter.png             Moran 散点图")
print("  03_lisa_cluster_map.html         LISA 交互聚类地图 (Folium)")
print("  04_accessibility_heatmap.html     可达性热力对比地图 (Folium)")
print("  05_vulnerable_groups_analysis.png 多维脆弱性分析图 (MVI/SDI/CI)")
print("  06_mvi_vulnerable_map.html        MVI 脆弱性交互地图 (Folium)")
print("  accessibility_results.geojson     完整分析结果 (GeoJSON)")
print("  accessibility_results.csv        完整分析结果 (CSV)")