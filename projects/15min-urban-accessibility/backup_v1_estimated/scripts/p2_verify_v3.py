# -*- coding: utf-8 -*-
"""
P2-V3: 使用真实人口数据的可达性分析
改进：
1. 使用估算的真实人口数据（基于南山区总人口160万 + 建筑面积比例）
2. 使用 v3 POI 数据（含高德API采集的夜间服务信息）
3. 改进的2SFCA方法
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
SEARCH_RADIUS_M = 1250
WALK_SPEED_M_PER_MIN = 83.33

# 南山区2023年常住人口（来自深圳统计年鉴）
NS_POPULATION_2023 = 1600000

def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlam = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
    return 2 * R * np.arcsin(np.sqrt(a))

# ============================================================
# Load POI
# ============================================================
print("Loading POI...")
# 使用 v3 数据（含高德API采集的夜间服务信息）
poi_path = os.path.join(BASE, 'osm_data', 'nanshan_poi_integrated_v3.csv')
if os.path.exists(poi_path):
    poi_df = pd.read_csv(poi_path, low_memory=False)
else:
    poi_df = pd.read_csv(os.path.join(BASE, 'osm_data', 'nanshan_poi_integrated_v2.csv'), low_memory=False)

poi_df = poi_df.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})

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

print(f"Total POI: {len(poi_df):,}")
print(f"night_service=True: {poi_df['night_service'].sum():,} ({100*poi_df['night_service'].mean():.1f}%)")

# ============================================================
# Load communities with REAL population
# ============================================================
print("\nLoading communities with real population...")

# 优先使用真实人口估算数据
pop_path = os.path.join(BASE, 'osm_data', 'nanshan_communities_real_population.csv')
if os.path.exists(pop_path):
    comm_df = pd.read_csv(pop_path)
    print(f"Loaded real population data: {len(comm_df)} communities")
    # 使用估算的真实人口
    if 'population_est' in comm_df.columns:
        pop_col = 'population_est'
    else:
        pop_col = 'population'
else:
    comm_df = pd.read_csv(os.path.join(BASE, 'osm_data', 'nanshan_villages_with_building.csv'))
    pop_col = 'population'
    print("Using fallback population data")

print(f"Communities: {len(comm_df)}")

# ============================================================
# Build OD matrix
# ============================================================
print("\nBuilding OD matrix (Haversine)...")
comm_coords = comm_df[['lng', 'lat']].values
poi_coords = poi_df[['lng', 'lat']].values

N = len(comm_df)
M = len(poi_df)
print(f"OD matrix: {N} x {M} = {N*M:,} cells")

od_matrix = np.zeros((N, M), dtype=np.float64)
for i in range(N):
    clat, clon = comm_coords[i, 1], comm_coords[i, 0]
    R = 6371000
    phi1 = np.radians(clat)
    plat = np.radians(poi_coords[:, 1])
    dphi = np.radians(poi_coords[:, 1] - clat)
    dlam = np.radians(poi_coords[:, 0] - clon)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(plat)*np.sin(dlam/2)**2
    od_matrix[i, :] = 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

print(f"OD range: [{od_matrix.min():.0f}m, {od_matrix.max():.0f}m]")
print(f"Within {SEARCH_RADIUS_M}m radius: {(od_matrix <= SEARCH_RADIUS_M).sum():,} ({100*(od_matrix <= SEARCH_RADIUS_M).sum() / od_matrix.size:.1f}%)")

# ============================================================
# 2SFCA
# ============================================================
class TwoStepFloatingCatchmentArea:
    def __init__(self, search_radius_m=1250, supply_col='supply', demand_col='population'):
        self.search_radius = search_radius_m
        self.supply_col = supply_col
        self.demand_col = demand_col

    def step1(self, communities_df, facilities_df, od_matrix):
        n_fac = len(facilities_df)
        supply = facilities_df[self.supply_col].values.astype(np.float64)
        reach_mask = (od_matrix <= self.search_radius)
        demand = communities_df[self.demand_col].values.astype(np.float64)
        total_demand = (reach_mask * demand[:, None]).sum(axis=0)
        R_j = np.where(total_demand > 0, supply / total_demand, 0.0)
        facilities_df = facilities_df.copy()
        facilities_df['_R_j'] = R_j
        return facilities_df, R_j

    def step2(self, communities_df, facilities_df, od_matrix, R_j):
        reach_mask = (od_matrix <= self.search_radius)
        A_i = (reach_mask * R_j[None, :]).sum(axis=1)
        communities_df = communities_df.copy()
        communities_df['A_i_2sfca'] = A_i
        A_max = max(A_i.max(), 1e-9)
        communities_df['A_i_2sfca_norm'] = A_i / A_max
        return communities_df

    def fit_transform(self, communities_df, facilities_df, od_matrix):
        facilities_df, R_j = self.step1(communities_df, facilities_df, od_matrix)
        communities_df = self.step2(communities_df, facilities_df, od_matrix, R_j)
        return communities_df, facilities_df

# ============================================================
# Multi-period 2SFCA
# ============================================================
print("\n" + "="*55)
print(f"P2-V3: Multi-period 2SFCA (Real Population: {NS_POPULATION_2023:,})")
print("="*55)

results = comm_df[['id', 'lng', 'lat']].copy().reset_index(drop=True)
results = results.rename(columns={'id': 'community_id'})

# 使用真实估算的人口
results['population'] = comm_df[pop_col].values

print(f"\n[INFO] Total population: {results['population'].sum():,}")
print(f"[INFO] Avg community population: {results['population'].mean():,.0f}")

# Day
print("\n[DAY] All POIs")
fac_day = poi_df[['supply']].copy()
comm_w = results[['community_id', 'population']].copy()
model = TwoStepFloatingCatchmentArea(search_radius_m=SEARCH_RADIUS_M, supply_col='supply')
comm_result_day, _ = model.fit_transform(comm_w, fac_day, od_matrix)
results = results.merge(comm_result_day[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']], on='community_id', how='left')
results = results.rename(columns={'A_i_2sfca': 'A_i_2sfca_day', 'A_i_2sfca_norm': 'A_i_2sfca_norm_day'})

# Night
night_poi = poi_df[poi_df['night_service'] == True].copy().reset_index(drop=True)
print(f"[NIGHT] Night-only POIs: {len(night_poi):,} ({100*len(night_poi)/len(poi_df):.1f}%)")

if len(night_poi) > 0:
    fac_night = night_poi[['supply']].copy()
    night_idx = poi_df[poi_df['night_service'] == True].index.tolist()
    od_night = od_matrix[:, night_idx]
    model2 = TwoStepFloatingCatchmentArea(search_radius_m=SEARCH_RADIUS_M, supply_col='supply')
    comm_result_night, _ = model2.fit_transform(comm_w, fac_night, od_night)
    results = results.merge(comm_result_night[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']], on='community_id', how='left')
    results = results.rename(columns={'A_i_2sfca': 'A_i_2sfca_night', 'A_i_2sfca_norm': 'A_i_2sfca_norm_night'})
else:
    results['A_i_2sfca_night'] = 0.0
    results['A_i_2sfca_norm_night'] = 0.0

# TPI
day_vals = results['A_i_2sfca_norm_day'].fillna(0.0)
night_vals = results['A_i_2sfca_norm_night'].fillna(0.0)
results['TPI'] = np.where(day_vals > 0, (night_vals - day_vals) / day_vals * 100, 0.0)
results['accessibility_gap'] = day_vals - night_vals
results['accessibility_ratio'] = np.where(day_vals > 0, night_vals / day_vals, 0.0)

def classify_tpi(tpi):
    if tpi >= 50: return '4-Severe Deprivation'
    if tpi >= 20: return '3-Moderate Deprivation'
    if tpi >= 5: return '2-Mild Deprivation'
    if tpi >= -5: return '1-No Significant'
    return '0-Night Advantage'

results['TPI_level'] = results['TPI'].apply(classify_tpi)

# ============================================================
# Summary
# ============================================================
print("\n" + "="*55)
print("P2-V3 RESULTS (Real Population Data)")
print("="*55)
print(f"Total population: {results['population'].sum():,}")
print(f"\nDay  accessibility: mean={day_vals.mean():.4f}, median={day_vals.median():.4f}, std={day_vals.std():.4f}")
print(f"Night accessibility: mean={night_vals.mean():.4f}, median={night_vals.median():.4f}, std={night_vals.std():.4f}")

print("\nTPI (Time Poverty Index):")
print(f"  mean={results['TPI'].mean():.1f}%, median={results['TPI'].median():.1f}%, std={results['TPI'].std():.1f}%")
print(f"  min={results['TPI'].min():.1f}%, max={results['TPI'].max():.1f}%")

print("\nTPI Level Distribution:")
for level, cnt in results['TPI_level'].value_counts().sort_index().items():
    print(f"  {level}: {cnt:3d} ({100*cnt/len(results):.1f}%)")

print("\nTop 10 by TPI (most night-deprived):")
cols = ['community_id', 'population', 'A_i_2sfca_norm_day', 'A_i_2sfca_norm_night', 'TPI', 'TPI_level']
print(results.nlargest(10, 'TPI')[cols].to_string(index=False))

# Save results
output_csv = os.path.join(BASE, 'p2_v3_results.csv')
results.to_csv(output_csv, index=False, encoding='utf-8-sig')
print(f"\n[OK] Results saved: {output_csv}")

# Night service by facility type
print("\nNight service by facility_type:")
for ft, grp in poi_df.groupby('facility_type'):
    n_night = grp['night_service'].sum()
    n_total = len(grp)
    if n_night > 0:
        print(f"  {ft}: {n_night:,} / {n_total:,} night ({100*n_night/n_total:.1f}%)")

print("\n*** P2-V3 COMPLETE ***")
print("Population data: Real (estimated from 1.6M Nanshan residents)")
print("POI data: v3 (with Gaode API night service)")
