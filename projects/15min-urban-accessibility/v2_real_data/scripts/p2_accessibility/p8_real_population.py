# -*- coding: utf-8 -*-
"""
P8: 数据清洗 + 路网构建 + 网络分析 (真实人口版)
===============================================
人口数据来源:
  - 南山区2025年初常住人口: 184.44万人
  - 来源: 深圳市南山区人民政府官网 https://www.szns.gov.cn/
  - 年份: 2025年数据

数据链路:
  1. 道路网络: 深圳路网数据.shp (南山区内截取) ✅
  2. 小区位置: sz_village_geocoded.csv (南山区内过滤) ✅
  3. 设施POI: nanshan_poi_integrated_v3.csv ✅
  4. 人口数据: 184.44万 × 建筑面积比例 ✅
  5. 网络分析: 真实步行网络距离 ✅
"""
import warnings, sys, io, os, time
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import networkx as nx
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import heapq

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
ROAD_DIR = os.path.join(BASE, "深圳路网数据")

# ============================================================
# 真实数据 (来源: 南山区人民政府 szns.gov.cn 2025年)
# ============================================================
NS_POPULATION_REAL = 1844400   # 南山区2025年初常住人口: 184.44万
NS_POP_YEAR = 2025             # 数据年份
NS_POP_SOURCE = "深圳市南山区人民政府 (szns.gov.cn)"
NS_AREA_KM2 = 187.53           # 管辖面积 km²
NS_POP_DENSITY_REPORTED = 9840 # 官方公布人口密度 人/km²

# 南山区范围
NS = {'west': 113.85, 'east': 114.05, 'south': 22.45, 'north': 22.65}
WALK_SPEED = 83.33   # m/min (5 km/h)
MAX_TIME_MIN = 15
MAX_DIST_M = MAX_TIME_MIN * WALK_SPEED

print("=" * 70)
print("P8: 网络可达性分析 (真实人口版)")
print("=" * 70)
print(f"人口数据来源: {NS_POP_SOURCE}")
print(f"南山区常住人口({NS_POP_YEAR}年初): {NS_POPULATION_REAL:,} (184.44万)")
print(f"管辖面积: {NS_AREA_KM2} km²")
print(f"官方人口密度: {NS_POP_DENSITY_REPORTED} 人/km²")
print(f"搜索半径: {MAX_DIST_M:.0f}m ({MAX_TIME_MIN}分钟步行)")
print("=" * 70)

# ============================================================
# Step 1: 加载路网
# ============================================================
print("\n[Step 1] 加载深圳路网并截取南山区")
print("-" * 50)
t0 = time.time()

road_shp = os.path.join(ROAD_DIR, [f for f in os.listdir(ROAD_DIR) if f.endswith('.shp')][0])
road_all = gpd.read_file(road_shp)
print(f"深圳全市: {len(road_all):,} 条")

road_ns = road_all.cx[NS['west']:NS['east'], NS['south']:NS['north']].copy()
road_ns = road_ns[road_ns.geometry.is_valid].reset_index(drop=True)
print(f"南山区: {len(road_ns):,} 条")

# 计算长度
def calc_length_m(row):
    try:
        coords = []
        if row.geometry.geom_type == 'LineString':
            coords = list(row.geometry.coords)
        elif row.geometry.geom_type == 'MultiLineString':
            for line in row.geometry.geoms:
                coords.extend(list(line.coords))
        if len(coords) < 2:
            return 0.0
        total = 0.0
        for i in range(len(coords) - 1):
            phi1, phi2 = np.radians(coords[i][1]), np.radians(coords[i+1][1])
            dphi = np.radians(coords[i+1][1] - coords[i][1])
            dlam = np.radians(coords[i+1][0] - coords[i][0])
            a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
            total += 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        return total
    except:
        return 0.0

road_ns['length_m'] = road_ns.apply(calc_length_m, axis=1)
total_road_len = road_ns['length_m'].sum()
print(f"南山区道路总长: {total_road_len/1000:.1f} km")
print(f"道路密度: {total_road_len/1000/NS_AREA_KM2:.1f} km/km²")

# ============================================================
# Step 2: 构建步行网络
# ============================================================
print("\n[Step 2] 构建步行网络图")
print("-" * 50)
t1 = time.time()

SPEED_ADJUST = {
    '人行道路': 1.0, '服务性道路': 0.9, '居住区道路': 0.85,
    '主要道路': 0.8, '次要道路': 0.85, '第三级道路': 0.85,
    '未分类道路': 0.8, '主要道路_连接': 0.8,
    '台阶踏步': 0.5, '自行车道': 0.6,
    '高架及快速路': 0.3, '公车专用道': 0.3, '郊区乡村道路': 0.5,
    '其它': 0.7, '城市主干路': 0.8, '城市次干路': 0.85,
    '城市支路': 0.9, '内部道路': 0.7,
}

def get_speed(fclass_cn, fclass_en):
    for k, v in SPEED_ADJUST.items():
        if k in str(fclass_cn):
            return WALK_SPEED * v
    return WALK_SPEED * 0.8

G = nx.DiGraph()
node_id_map = {}
nodes_data = []

def add_node(lon, lat):
    key = (round(lon, 7), round(lat, 7))
    if key not in node_id_map:
        nid = len(node_id_map)
        node_id_map[key] = nid
        nodes_data.append((nid, lon, lat))
    return node_id_map[key]

edge_count = 0
for _, row in road_ns.iterrows():
    speed = get_speed(row.get('fclass_cn', ''), row.get('fclass', ''))
    if speed < WALK_SPEED * 0.4:
        continue
    geom = row.geometry
    if geom.geom_type == 'LineString':
        coords = list(geom.coords)
    elif geom.geom_type == 'MultiLineString':
        coords = []
        for line in geom.geoms:
            coords.extend(list(line.coords))
    else:
        continue
    if len(coords) < 2:
        continue

    nid_prev = None
    prev_lon, prev_lat = None, None
    for lon, lat in coords:
        nid = add_node(lon, lat)
        if nid_prev is not None:
            phi1, phi2 = np.radians(prev_lat), np.radians(lat)
            dphi = np.radians(lat - prev_lat)
            dlam = np.radians(lon - prev_lon)
            a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
            seg_len = 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            tt = seg_len / speed
            oneway = str(row.get('oneway', 'no')).lower()
            is_ow = oneway in ['yes', 'true', '1']
            G.add_edge(nid_prev, nid, length=seg_len, time=tt)
            edge_count += 1
            if not is_ow:
                G.add_edge(nid, nid_prev, length=seg_len, time=tt)
                edge_count += 1
        nid_prev = nid
        prev_lon, prev_lat = lon, lat

largest_cc = max(nx.weakly_connected_components(G), key=len)
G_main = G.subgraph(largest_cc).copy()
print(f"节点: {G_main.number_of_nodes():,}, 边: {G_main.number_of_edges():,}")
print(f"[耗时 {time.time()-t1:.1f}s]")

# ============================================================
# Step 3: 小区和POI匹配
# ============================================================
print("\n[Step 3] 小区和POI匹配到网络节点")
print("-" * 50)
t2 = time.time()

nodes_df = pd.DataFrame(nodes_data, columns=['node_id', 'lon', 'lat'])
nodes_df = nodes_df[nodes_df['node_id'].isin(set(G_main.nodes()))]
nodes_coords = nodes_df[['lon', 'lat']].values
node_tree = cKDTree(nodes_coords)

# 小区
comm_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_villages_with_building.csv"))
comm_df = comm_df[
    (comm_df['lng'] >= NS['west']) & (comm_df['lng'] <= NS['east']) &
    (comm_df['lat'] >= NS['south']) & (comm_df['lat'] <= NS['north'])
].copy().reset_index(drop=True)
print(f"南山区小区: {len(comm_df)}")

# 用真实人口估算
pop_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_communities_real_population.csv"))
pop_df = pop_df.rename(columns={'id': 'community_id'})

comm_df = comm_df.merge(
    pop_df[['community_id', 'population_est', 'community_type', 'area_m2']],
    left_on='id', right_on='community_id', how='left', suffixes=('', '_pop')
)

# 关键修正: 按真实总人口归一化
# 旧估算总量: 1,599,796 -> 新总量: 1,844,400
OLD_TOTAL = 1599796
pop_scale = NS_POPULATION_REAL / OLD_TOTAL
comm_df['population_est'] = (comm_df['population_est'] * pop_scale).fillna(comm_df['population_est'] * pop_scale).astype(int)
print(f"人口修正: {OLD_TOTAL:,} -> {comm_df['population_est'].sum():,}")
print(f"人均修正: ×{pop_scale:.4f}")

# POI
poi_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_poi_integrated_v3.csv"), low_memory=False)
poi_df = poi_df.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})
poi_df = poi_df[
    (poi_df['lng'] >= NS['west']) & (poi_df['lng'] <= NS['east']) &
    (poi_df['lat'] >= NS['south']) & (poi_df['lat'] <= NS['north'])
].copy().reset_index(drop=True)
print(f"南山区POI: {len(poi_df):,}")

# 匹配
dist_c, idx_c = node_tree.query(comm_df[['lng', 'lat']].values, k=1)
comm_df['nearest_node'] = nodes_df.iloc[idx_c]['node_id'].values
comm_df['snap_dist_m'] = dist_c

dist_p, idx_p = node_tree.query(poi_df[['lng', 'lat']].values, k=1)
poi_df['nearest_node'] = nodes_df.iloc[idx_p]['node_id'].values
poi_df['snap_dist_m'] = dist_p

print(f"小区匹配: avg={comm_df['snap_dist_m'].mean():.1f}m")
print(f"POI匹配: avg={poi_df['snap_dist_m'].mean():.1f}m")
print(f"[耗时 {time.time()-t2:.1f}s]")

# ============================================================
# Step 4: 网络可达性计算
# ============================================================
print("\n[Step 4] 计算网络可达性 (2SFCA)")
print("-" * 50)
t3 = time.time()

poi_df['supply'] = 1.0
facility_supply = poi_df['supply'].values
poi_nodes = poi_df['nearest_node'].values
comm_nodes = comm_df['nearest_node'].values
comm_pops = comm_df['population_est'].values
night_mask = poi_df['night_service_final'].astype(bool).values

G_und = G_main.to_undirected()

# 设施节点
fac_nodes_unique = sorted(set(poi_nodes))
fac_node_to_idx = {fn: i for i, fn in enumerate(fac_nodes_unique)}

# 小区人口字典
comm_pop_dict = {nid: (i, pop) for i, (nid, pop) in enumerate(zip(comm_nodes, comm_pops)) if nid in G_und}

def dijkstra_reach_pop(start_node, max_dist):
    if start_node not in G_und:
        return 0.0
    dist_map = {start_node: 0.0}
    pq = [(0.0, start_node)]
    total_pop = 0.0
    visited = 0
    while pq and visited < 5000:
        d, node = heapq.heappop(pq)
        if d > max_dist:
            break
        if d > dist_map.get(node, float('inf')):
            continue
        visited += 1
        if node in comm_pop_dict:
            total_pop += comm_pop_dict[node][1]
        for neighbor in G_und.neighbors(node):
            edge_len = G_und[node][neighbor].get('length', 10.0)
            nd = d + edge_len
            if nd < dist_map.get(neighbor, float('inf')) and nd <= max_dist:
                dist_map[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
    return total_pop

# R_j: 设施服务能力 (Step1)
print("计算设施吸引力 R_j...")
R_j_all = np.zeros(len(fac_nodes_unique))
R_j_night = np.zeros(len(fac_nodes_unique))

# 日间设施吸引力
for fi, fnode in enumerate(fac_nodes_unique):
    p_reach = dijkstra_reach_pop(fnode, MAX_DIST_M)
    poi_idx = list(poi_nodes).index(fnode)
    R_j_all[fi] = facility_supply[poi_idx] / max(p_reach, 1)

# 夜间设施吸引力
night_fac_nodes = sorted(set(poi_nodes[i] for i in range(len(poi_nodes)) if night_mask[i]))
night_fac_node_to_idx = {fn: i for i, fn in enumerate(night_fac_nodes)}

for fi, fnode in enumerate(night_fac_nodes):
    p_reach = dijkstra_reach_pop(fnode, MAX_DIST_M)
    poi_idx = [i for i in range(len(poi_nodes)) if poi_nodes[i] == fnode and night_mask[i]][0]
    R_j_night[fi] = facility_supply[poi_idx] / max(p_reach, 1)

# 建立 node -> {fac_idx: R_j} 映射
node_fac_R = defaultdict(dict)
node_fac_R_night = defaultdict(dict)
for poi_i, fnode in enumerate(poi_nodes):
    if R_j_all[fac_node_to_idx[fnode]] > 0:
        node_fac_R[fnode][poi_i] = R_j_all[fac_node_to_idx[fnode]]
    if night_mask[poi_i]:
        if fnode in night_fac_node_to_idx:
            ridx = night_fac_node_to_idx[fnode]
            if R_j_night[ridx] > 0:
                node_fac_R_night[fnode][poi_i] = R_j_night[ridx]

# Step2: 计算小区可达性
print(f"计算 {len(comm_df)} 个小区的可达性...")

def calc_access(cnid, node_R_map):
    if cnid not in G_und:
        return 0.0
    dist_map = {cnid: 0.0}
    pq = [(0.0, cnid)]
    acc = 0.0
    visited = 0
    while pq and visited < 5000:
        d, node = heapq.heappop(pq)
        if d > MAX_DIST_M:
            break
        if d > dist_map.get(node, float('inf')):
            continue
        visited += 1
        if node in node_R_map:
            acc += sum(node_R_map[node].values())
        for neighbor in G_und.neighbors(node):
            edge_len = G_und[node][neighbor].get('length', 10.0)
            nd = d + edge_len
            if nd < dist_map.get(neighbor, float('inf')) and nd <= MAX_DIST_M:
                dist_map[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
    return acc

def worker(i):
    cnid = comm_nodes[i]
    a_d = calc_access(cnid, node_fac_R)
    a_n = calc_access(cnid, node_fac_R_night)
    return i, a_d, a_n

res_d = np.zeros(len(comm_df))
res_n = np.zeros(len(comm_df))

with ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(worker, i) for i in range(len(comm_df))]
    done = 0
    for f in futures:
        i, ad, an = f.result()
        res_d[i] = ad
        res_n[i] = an
        done += 1
        if done % 50 == 0:
            print(f"  {done}/{len(comm_df)} ({100*done/len(comm_df):.0f}%)")

# 归一化
dmax = max(res_d.max(), 1e-9)
nmax = max(res_n.max(), 1e-9)
res_d_n = res_d / dmax
res_n_n = res_n / nmax

print(f"[耗时 {time.time()-t3:.1f}s]")

# ============================================================
# Step 5: 结果计算
# ============================================================
print("\n[Step 5] TPI + SAII")
print("-" * 50)

results = comm_df[['id', 'lng', 'lat', 'population_est', 'community_type', 'area_m2']].copy()
results = results.rename(columns={
    'id': 'community_id',
    'population_est': 'population'
})
results['A_day_raw'] = res_d
results['A_night_raw'] = res_n
results['A_day_norm'] = res_d_n
results['A_night_norm'] = res_n_n

# TPI
results['TPI'] = np.where(res_d_n > 0, (res_n_n - res_d_n) / res_d_n * 100, 0.0)
results['accessibility_gap'] = res_d_n - res_n_n
results['accessibility_ratio'] = np.where(res_d_n > 0, res_n_n / res_d_n, 0.0)
results['SAII'] = results['A_day_norm'] * results['TPI'].abs() / 100

def classify_tpi(tpi):
    if tpi >= 50: return '4-Severe'
    if tpi >= 20: return '3-Moderate'
    if tpi >= 5: return '2-Mild'
    if tpi >= -5: return '1-None'
    return '0-NightAdv'

results['TPI_level'] = results['TPI'].apply(classify_tpi)

# 保存
output = os.path.join(BASE, "p8_network_results.csv")
results.to_csv(output, index=False, encoding='utf-8-sig')
print(f"[OK] 保存: {output}")

# ============================================================
# 结果输出
# ============================================================
print("\n" + "=" * 70)
print("P8 分析结果 (真实人口数据)")
print("=" * 70)
print(f"\n数据来源:")
print(f"  人口: {NS_POPULATION_REAL:,} ({NS_POP_YEAR}年初, 来源: {NS_POP_SOURCE})")
print(f"  面积: {NS_AREA_KM2} km²")
print(f"  密度: {NS_POP_DENSITY_REPORTED} 人/km²")

print(f"\n网络:")
print(f"  节点: {G_main.number_of_nodes():,}")
print(f"  边: {G_main.number_of_edges():,}")
print(f"  道路: {len(road_ns):,} 条, {total_road_len/1000:.1f} km")
print(f"  密度: {total_road_len/1000/NS_AREA_KM2:.1f} km/km²")

print(f"\n小区: {len(results)}, 总人口: {results['population'].sum():,}")
print(f"POI: {len(poi_df):,} (日), {night_mask.sum():,} (夜)")

print(f"\n可达性:")
print(f"  日间: mean={res_d_n.mean():.4f}, median={np.median(res_d_n):.4f}")
print(f"  夜间: mean={res_n_n.mean():.4f}, median={np.median(res_n_n):.4f}")

print(f"\nTPI (时间贫困指数):")
print(f"  均值: {results['TPI'].mean():.1f}%")
print(f"  中位数: {results['TPI'].median():.1f}%")
print(f"  范围: [{results['TPI'].min():.1f}%, {results['TPI'].max():.1f}%]")

print(f"\nTPI等级分布:")
for lv, cnt in results['TPI_level'].value_counts().sort_index().items():
    pop_lv = results[results['TPI_level']==lv]['population'].sum()
    print(f"  {lv}: {cnt}个小区, {pop_lv:,}人 ({100*pop_lv/results['population'].sum():.1f}%)")

print(f"\n受影响人口 (轻度+中度+严重):")
affected = results[results['TPI'] > 5]
affected_pop = affected['population'].sum()
print(f"  小区: {len(affected)} ({100*len(affected)/len(results):.1f}%)")
print(f"  人口: {affected_pop:,} ({100*affected_pop/results['population'].sum():.1f}%)")

print(f"\nTop 10 时间贫困小区:")
cols = ['community_id', 'population', 'A_day_norm', 'A_night_norm', 'TPI', 'SAII']
print(results.nlargest(10, 'TPI')[cols].to_string(index=False))

print(f"\n总耗时: {time.time()-t0:.1f}s")
print("\n*** P8 COMPLETE ***")
print(f"数据来源: {NS_POP_SOURCE}")
print(f"南山区常住人口({NS_POP_YEAR}年初): {NS_POPULATION_REAL:,}")
