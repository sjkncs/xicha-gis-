# -*- coding: utf-8 -*-
"""P2: Standalone verification of multi-period 2SFCA"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree
import osmnx as ox
import networkx as nx
from shapely.geometry import Point

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.chdir(BASE)
SEARCH_RADIUS_M = 1250

# ============================================================
# Step 1: Check POI coordinates
# ============================================================
print("Loading POI data...")
poi_raw = pd.read_csv(os.path.join(BASE, 'osm_data', 'nanshan_poi_integrated_v2.csv'), low_memory=False)
print("Total records: {:,}".format(len(poi_raw)))
print("Columns: " + str(poi_raw.columns.tolist()))
if 'gcj_lon' in poi_raw.columns:
    print("gcj_lon: [{:.4f}, {:.4f}]".format(poi_raw['gcj_lon'].min(), poi_raw['gcj_lon'].max()))
    print("gcj_lat: [{:.4f}, {:.4f}]".format(poi_raw['gcj_lat'].min(), poi_raw['gcj_lat'].max()))

# ============================================================
# Step 2: Determine BBOX from POI data
# ============================================================
NS_S = float(poi_raw['gcj_lat'].min() - 0.01)
NS_N = float(poi_raw['gcj_lat'].max() + 0.01)
NS_W = float(poi_raw['gcj_lon'].min() - 0.01)
NS_E = float(poi_raw['gcj_lon'].max() + 0.01)
print("\nNanshan BBOX (GCJ-02):")
print("  South: {:.4f}, North: {:.4f}".format(NS_S, NS_N))
print("  West:  {:.4f}, East:  {:.4f}".format(NS_W, NS_E))

# ============================================================
# Step 3: Filter POI
# ============================================================
poi_df = poi_raw.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})
poi_df = poi_df[
    (poi_df['lng'] > NS_W) & (poi_df['lng'] < NS_E) &
    (poi_df['lat'] > NS_S) & (poi_df['lat'] < NS_N)
].copy().reset_index(drop=True)
print("\nPOI within BBOX: {:,}".format(len(poi_df)))

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
    return SUPPLY_MAP.get(str(ftype), 1.0)

poi_df['supply'] = poi_df['facility_type'].apply(get_supply).clip(0.3, 2.0)
poi_df['night_service'] = poi_df['night_service_final'].astype(bool)
print("night_service=True: {:,} ({:.1f}%)".format(
    poi_df['night_service'].sum(), 100*poi_df['night_service'].mean()))

# ============================================================
# Step 4: Load communities
# ============================================================
print("\nLoading communities...")
comm_df = pd.read_csv(os.path.join(BASE, 'osm_data', 'nanshan_villages_with_building.csv'))
print("Communities: {:,}".format(len(comm_df)))

# ============================================================
# Step 5: Load walk network
# ============================================================
print("\nLoading walk network...")
GML_PATH = os.path.join(BASE, 'osm_data', 'nanshan_walk_network.graphml')
if os.path.exists(GML_PATH):
    G_walk = ox.load_graphml(GML_PATH)
    print("Loaded: {:,} nodes, {:,} edges".format(len(G_walk.nodes), len(G_walk.edges)))
else:
    print("GraphML not found, downloading...")
    BBOX_TUPLE = (NS_N, NS_S, NS_W, NS_E)
    G_walk = ox.graph_from_bbox(bbox=BBOX_TUPLE, network_type='walk')
    ox.save_graphml(G_walk, GML_PATH)
    print("Downloaded: {:,} nodes, {:,} edges".format(len(G_walk.nodes), len(G_walk.edges)))

# Project nodes to UTM
nodes_gdf = ox.graph_to_gdfs(G_walk, nodes=True, edges=False)
nodes_gdf_proj = nodes_gdf.to_crs('EPSG:32650')
node_centroids = np.array([(g.centroid.x, g.centroid.y) for g in nodes_gdf_proj.geometry.values])
node_lons = nodes_gdf.geometry.x.values
node_lats = nodes_gdf.geometry.y.values
node_ids = list(G_walk.nodes)

node_tree = cKDTree(node_centroids)

# ============================================================
# Step 6: Build OD matrix
# ============================================================
print("\nBuilding OD matrix...")
SAMPLE_N = min(50, len(comm_df))
SAMPLE_POI = min(200, len(poi_df))
sample_comms = comm_df.head(SAMPLE_N).copy().reset_index(drop=True)
sample_poi = poi_df.head(SAMPLE_POI).copy().reset_index(drop=True)

sample_comms['node_idx'] = sample_comms.apply(
    lambda r: node_tree.query([r['lon'], r['lat']])[1], axis=1
)
sample_poi['poi_node_idx'] = sample_poi.apply(
    lambda r: node_tree.query([r['lng'], r['lat']])[1], axis=1
)

od_matrix = np.full((SAMPLE_N, SAMPLE_POI), np.inf, dtype=np.float64)
for i in range(SAMPLE_N):
    c_node = node_ids[sample_comms['node_idx'].iloc[i]]
    lengths = nx.single_source_dijkstra_path_length(G_walk, c_node, weight='length')
    for j in range(SAMPLE_POI):
        p_node = node_ids[sample_poi['poi_node_idx'].iloc[j]]
        if p_node in lengths:
            od_matrix[i, j] = lengths[p_node]

finite_count = np.isfinite(od_matrix).sum()
total = od_matrix.size
od_min = np.where(np.isfinite(od_matrix), od_matrix, np.inf).min()
od_max = od_matrix.max()
print("OD matrix: {} (finite: {:,} / {}, {:.0f}m to {:.0f}m)".format(
    od_matrix.shape, finite_count, total, od_min, od_max))

# ============================================================
# Step 7: 2SFCA (vectorized, from Cell 19)
# ============================================================
class TwoStepFloatingCatchmentArea:
    def __init__(self, search_radius_m=1250, supply_col='supply', demand_col='population'):
        self.search_radius = search_radius_m
        self.supply_col = supply_col
        self.demand_col = demand_col

    def step1(self, facilities_df, od_matrix):
        supply = facilities_df[self.supply_col].values.astype(np.float64)
        reach_mask = (od_matrix <= self.search_radius) & np.isfinite(od_matrix)
        demand = facilities_df[self.demand_col].values.astype(np.float64)
        total_demand = (reach_mask * demand[:, None]).sum(axis=0)
        R_j = np.where(total_demand > 0, supply / total_demand, 0.0)
        return R_j

    def step2(self, communities_df, R_j, od_matrix):
        reach_mask = (od_matrix <= self.search_radius) & np.isfinite(od_matrix)
        A_i = (reach_mask * R_j[None, :]).sum(axis=1)
        return A_i

    def fit_transform(self, communities_df, facilities_df, od_matrix):
        R_j = self.step1(facilities_df, od_matrix)
        A_i = self.step2(communities_df, R_j, od_matrix)
        communities_df = communities_df.copy()
        communities_df['A_i_2sfca'] = A_i
        A_max = max(A_i.max(), 1e-9)
        communities_df['A_i_2sfca_norm'] = A_i / A_max
        return communities_df

# ============================================================
# Step 8: P2 Multi-period 2SFCA (fixed Cell 25)
# ============================================================
print("\n" + "="*55)
print("P2: Multi-period 2SFCA")
print("="*55)

results = sample_comms[['community_id', 'lon', 'lat']].copy()
results['population'] = np.random.randint(500, 5000, size=len(results))

for period in ['day', 'night']:
    print("\n[{}] Period...".format(period.upper()))
    
    if period == 'day':
        period_poi = sample_poi.copy()
        period_poi['effective_supply'] = period_poi['supply']
        od_period = od_matrix
    else:
        night_mask = sample_poi['night_service'] == True
        period_poi = sample_poi[night_mask].copy().reset_index(drop=True)
        
        if len(period_poi) == 0:
            results['A_i_2sfca_{}'.format(period)] = 0.0
            results['A_i_2sfca_norm_{}'.format(period)] = 0.0
            print("  [WARN] No night facilities!")
            continue
        
        period_poi['effective_supply'] = period_poi['supply']
        night_idx = sample_poi[night_mask].index.tolist()
        od_period = od_matrix[:, night_idx]
    
    print("  POIs: {}, supply range: [{:.2f}, {:.2f}]".format(
        len(period_poi),
        period_poi['effective_supply'].min(),
        period_poi['effective_supply'].max()))
    
    fac_df = period_poi[['effective_supply']].copy()
    fac_df['population'] = 1.0
    comm_df_w = results[['community_id', 'population']].copy()
    
    model = TwoStepFloatingCatchmentArea(
        search_radius_m=SEARCH_RADIUS_M,
        supply_col='effective_supply',
        demand_col='population'
    )
    comm_result = model.fit_transform(comm_df_w, fac_df, od_period)
    
    results = results.merge(
        comm_result[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']],
        on='community_id', how='left'
    )
    results = results.rename(columns={
        'A_i_2sfca': 'A_i_2sfca_{}'.format(period),
        'A_i_2sfca_norm': 'A_i_2sfca_norm_{}'.format(period)
    })

# TPI calculation
day_vals   = results['A_i_2sfca_norm_day'].fillna(0.0)
night_vals = results['A_i_2sfca_norm_night'].fillna(0.0)

results['TPI'] = np.where(day_vals > 0, (night_vals - day_vals) / day_vals * 100, 0.0)
results['accessibility_gap'] = day_vals - night_vals
results['accessibility_ratio'] = np.where(
    day_vals > 0, night_vals / day_vals, 0.0
)

def classify_tpi(tpi):
    if tpi >= 50: return '4-Severe Deprivation'
    if tpi >= 20: return '3-Moderate Deprivation'
    if tpi >= 5:  return '2-Mild Deprivation'
    if tpi >= -5: return '1-No Significant'
    return '0-Night Advantage'

results['TPI_level'] = results['TPI'].apply(classify_tpi)

# ============================================================
# Results
# ============================================================
print("\n" + "="*55)
print("RESULTS SUMMARY")
print("="*55)
print("Day  Accessibility:  mean={:.4f}, median={:.4f}".format(day_vals.mean(), day_vals.median()))
print("Night Accessibility: mean={:.4f}, median={:.4f}".format(night_vals.mean(), night_vals.median()))
night_poi_n = len(sample_poi[sample_poi['night_service'] == True])
print("Night POIs: {:,} / {:,} ({:.1f}%)".format(
    night_poi_n, len(sample_poi), 100*night_poi_n/len(sample_poi)))
print("\nTPI: mean={:.1f}%, median={:.1f}%, range=[{:.1f}%, {:.1f}%]".format(
    results['TPI'].mean(), results['TPI'].median(),
    results['TPI'].min(), results['TPI'].max()))
print("\nTPI Level Distribution:")
for level, cnt in results['TPI_level'].value_counts().sort_index().items():
    print("  {}: {} ({:.1f}%)".format(level, cnt, 100*cnt/len(results)))

print("\nTop 5 by TPI (most night-deprived):")
cols = ['community_id', 'A_i_2sfca_norm_day', 'A_i_2sfca_norm_night', 'TPI', 'TPI_level']
print(results.nlargest(5, 'TPI')[cols].to_string(index=False))

print("\n*** P2 VERIFICATION COMPLETE ***")
