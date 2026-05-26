# -*- coding: utf-8 -*-
"""
P7: 数据清洗 + 路网构建 + 网络分析 (完整版)
基于深圳路网数据构建真实步行网络，计算网络可达性

科学链路:
1. 清洗: 只保留南山区分数据
2. 路网: 深圳路网数据.shp截取南山区
3. 网络: 构建步行网络图(OSMNX风格)
4. 距离: 真实步行距离(而非Haversine直线)
5. 可达性: 2SFCA + TPI + SAII
"""
import warnings, sys, io, os, time
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, MultiLineString
import networkx as nx
from scipy.spatial import cKDTree
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.patches import FancyBboxPatch
from collections import defaultdict

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
ROAD_DIR = os.path.join(BASE, "深圳路网数据")

# 南山区范围
NS = {'west': 113.85, 'east': 114.05, 'south': 22.45, 'north': 22.65}
# 步行速度 m/min (5km/h = 83.33 m/min)
WALK_SPEED = 83.33
# 最大步行时间 (15分钟 = 1250m)
MAX_TIME_MIN = 15
MAX_DIST_M = MAX_TIME_MIN * WALK_SPEED

print("=" * 70)
print("P7: 数据清洗 + 路网分析 + 网络可达性")
print("=" * 70)
print(f"南山区范围: lon[{NS['west']},{NS['east']}] lat[{NS['south']},{NS['north']}]")

# ============================================================
# Step 1: 加载深圳路网并截取南山区
# ============================================================
print("\n[Step 1] 加载深圳路网并截取南山区")
print("-" * 50)
t0 = time.time()

road_shp = os.path.join(ROAD_DIR, [f for f in os.listdir(ROAD_DIR) if f.endswith('.shp')][0])
road_all = gpd.read_file(road_shp)
print(f"深圳全市道路: {len(road_all):,} 条")
print(f"CRS: {road_all.crs}")

# 截取南山区
road_ns = road_all.cx[NS['west']:NS['east'], NS['south']:NS['north']].copy()
road_ns = road_ns[road_ns.geometry.is_valid].reset_index(drop=True)
print(f"南山区道路: {len(road_ns):,} 条")

# 道路类型(中文)
fclass_cn = road_ns['fclass_cn'].value_counts() if 'fclass_cn' in road_ns.columns else pd.Series()
fclass_en = road_ns['fclass'].value_counts() if 'fclass' in road_ns.columns else pd.Series()
print(f"\n道路类型分布:")
combined = pd.concat([fclass_cn, fclass_en], axis=0)
for k, v in combined.head(10).items():
    if pd.notna(k):
        print(f"  {k}: {v:,}")

# 计算每段道路长度(米)
def calc_length_m(row):
    try:
        if row.geometry.geom_type == 'LineString':
            coords = row.geometry.coords
            if len(coords) < 2:
                return 0.0
            total = 0.0
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[i+1]
                phi1, phi2 = np.radians(lat1), np.radians(lat2)
                dphi = np.radians(lat2 - lat1)
                dlam = np.radians(lon2 - lon1)
                a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
                total += 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            return total
        elif row.geometry.geom_type == 'MultiLineString':
            total = 0.0
            for line in row.geometry.geoms:
                coords = list(line.coords)
                for i in range(len(coords) - 1):
                    lon1, lat1 = coords[i]
                    lon2, lat2 = coords[i+1]
                    phi1, phi2 = np.radians(lat1), np.radians(lat2)
                    dphi = np.radians(lat2 - lat1)
                    dlam = np.radians(lon2 - lon1)
                    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
                    total += 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            return total
        return 0.0
    except:
        return 0.0

road_ns['length_m'] = road_ns.apply(calc_length_m, axis=1)
total_road_len = road_ns['length_m'].sum()
print(f"\n南山区道路总长度: {total_road_len/1000:.1f} km")
print(f"道路密度: {total_road_len/1000/187.53:.1f} km/km²")

# 保存清洗后的路网
road_ns.to_file(os.path.join(BASE, "osm_data/nanshan_road_network.shp"))
print(f"[OK] 保存: osm_data/nanshan_road_network.shp")

print(f"\n[Step 1 完成, 耗时 {time.time()-t0:.1f}s]")

# ============================================================
# Step 2: 构建路网图
# ============================================================
print("\n[Step 2] 构建步行网络图")
print("-" * 50)
t1 = time.time()

# 创建步行网络图
# 策略: 将所有道路端点作为节点, 道路作为边
# 步行速度按道路类型调整
SPEED_ADJUST = {
    '人行道路': 1.0,   # 基准
    '城市支路': 0.9,
    '城市次干路': 0.85,
    '城市主干路': 0.8,
    '城市支路': 0.9,
    '内部道路': 0.7,
    '自行车道': 0.6,
    '高架及快速路': 0.3,  # 不适合步行
    '公车专用道': 0.3,
    '郊区乡村道路': 0.5,
    '其它': 0.8,
}

def get_walk_speed(fclass_cn_val, fclass_en_val):
    fc = str(fclass_cn_val) if pd.notna(fclass_cn_val) else ''
    for k, v in SPEED_ADJUST.items():
        if k in fc:
            return WALK_SPEED * v
    # 按英文类型
    fe = str(fclass_en_val) if pd.notna(fclass_en_val) else ''
    if 'footway' in fe.lower() or 'pedestrian' in fe.lower():
        return WALK_SPEED * 1.0
    if 'residential' in fe.lower():
        return WALK_SPEED * 0.85
    if 'tertiary' in fe.lower():
        return WALK_SPEED * 0.8
    if 'secondary' in fe.lower():
        return WALK_SPEED * 0.75
    if 'primary' in fe.lower():
        return WALK_SPEED * 0.7
    if 'motorway' in fe.lower() or 'trunk' in fe.lower():
        return WALK_SPEED * 0.3
    return WALK_SPEED * 0.8

# 构建图
G = nx.DiGraph()  # 有向图(处理单行道)

node_id_map = {}  # (lon, lat) -> node_id
nodes_data = []  # node_id -> (lon, lat)

def add_node(lon, lat):
    key = (round(lon, 7), round(lat, 7))
    if key not in node_id_map:
        nid = len(node_id_map)
        node_id_map[key] = nid
        nodes_data.append((nid, lon, lat))
    return node_id_map[key]

edge_count = 0
skipped_highway = 0

for _, row in road_ns.iterrows():
    fc_cn = row.get('fclass_cn', '')
    fc_en = row.get('fclass', '')

    # 跳过不适合步行的道路
    speed = get_walk_speed(fc_cn, fc_en)
    if speed < WALK_SPEED * 0.4:
        skipped_highway += 1
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

    # 添加节点
    nid_prev = None
    cum_dist = 0.0
    prev_lon, prev_lat = None, None

    for lon, lat in coords:
        nid = add_node(lon, lat)

        if nid_prev is not None:
            # Haversine 段长度
            phi1, phi2 = np.radians(prev_lat), np.radians(lat)
            dphi = np.radians(lat - prev_lat)
            dlam = np.radians(lon - prev_lon)
            a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlam/2)**2
            seg_len = 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
            cum_dist += seg_len

            travel_time = seg_len / speed

            # 判断方向
            oneway = str(row.get('oneway', 'no')).lower()
            is_oneway = oneway in ['yes', 'true', '1']

            # 正向边
            G.add_edge(nid_prev, nid, length=seg_len, time=travel_time, speed=speed)
            edge_count += 1

            # 反向边 (双向)
            if not is_oneway:
                G.add_edge(nid, nid_prev, length=seg_len, time=travel_time, speed=speed)
                edge_count += 1

        nid_prev = nid
        prev_lon, prev_lat = lon, lat

print(f"添加节点: {G.number_of_nodes():,}")
print(f"添加边: {G.number_of_edges():,} (含双向)")
print(f"跳过不适合步行的路段: {skipped_highway:,}")
print(f"平均节点度: {2*G.number_of_edges()/G.number_of_nodes():.2f}")

# 清理悬挂节点(度=1的叶子节点)
# 保留连通分量
if G.number_of_nodes() > 0:
    largest_cc = max(nx.weakly_connected_components(G), key=len)
    G_main = G.subgraph(largest_cc).copy()
else:
    G_main = G

print(f"最大连通分量: {G_main.number_of_nodes():,} 节点, {G_main.number_of_edges():,} 边")
print(f"[Step 2 完成, 耗时 {time.time()-t1:.1f}s]")

# 保存节点数据
nodes_df = pd.DataFrame(nodes_data, columns=['node_id', 'lon', 'lat'])
nodes_df = nodes_df[nodes_df['node_id'].isin(set(G_main.nodes()))]
nodes_df.to_csv(os.path.join(BASE, "osm_data/nanshan_network_nodes.csv"), index=False)
print(f"[OK] 保存节点: osm_data/nanshan_network_nodes.csv")

# ============================================================
# Step 3: 加载小区和POI, 匹配到最近网络节点
# ============================================================
print("\n[Step 3] 小区和POI匹配到网络节点")
print("-" * 50)
t2 = time.time()

# 小区数据
comm_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_villages_with_building.csv"))
# 确保只保留南山区
comm_df = comm_df[
    (comm_df['lng'] >= NS['west']) & (comm_df['lng'] <= NS['east']) &
    (comm_df['lat'] >= NS['south']) & (comm_df['lat'] <= NS['north'])
].copy().reset_index(drop=True)
print(f"南山区小区: {len(comm_df)}")

# 人口数据
pop_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_communities_real_population.csv"))
if 'community_type' in pop_df.columns:
    pop_df = pop_df.rename(columns={'id': 'community_id'})
    pop_df = pop_df.rename(columns={'housetitle': 'name'})
else:
    pop_df = pop_df.rename(columns={'id': 'community_id'})

# 合并人口
comm_df = comm_df.merge(pop_df[['community_id', 'population_est', 'community_type', 'area_m2']],
                          left_on='id', right_on='community_id', how='left', suffixes=('', '_pop'))

# POI数据
poi_df = pd.read_csv(os.path.join(BASE, "osm_data/nanshan_poi_integrated_v3.csv"), low_memory=False)
poi_df = poi_df.rename(columns={'gcj_lon': 'lng', 'gcj_lat': 'lat'})
poi_df = poi_df[
    (poi_df['lng'] >= NS['west']) & (poi_df['lng'] <= NS['east']) &
    (poi_df['lat'] >= NS['south']) & (poi_df['lat'] <= NS['north'])
].copy().reset_index(drop=True)
print(f"南山区POI: {len(poi_df):,}")

# 匹配到最近节点 (使用KDTree加速)
nodes_coords = nodes_df[['lon', 'lat']].values
node_tree = cKDTree(nodes_coords)

# 小区 -> 最近节点
dist_comm, idx_comm = node_tree.query(comm_df[['lng', 'lat']].values, k=1)
comm_df['nearest_node'] = nodes_df.iloc[idx_comm]['node_id'].values
comm_df['snap_dist_m'] = dist_comm

# POI -> 最近节点
dist_poi, idx_poi = node_tree.query(poi_df[['lng', 'lat']].values, k=1)
poi_df['nearest_node'] = nodes_df.iloc[idx_poi]['node_id'].values
poi_df['snap_dist_m'] = dist_poi

print(f"小区平均匹配距离: {comm_df['snap_dist_m'].mean():.1f}m (最大: {comm_df['snap_dist_m'].max():.1f}m)")
print(f"POI平均匹配距离: {poi_df['snap_dist_m'].mean():.1f}m (最大: {poi_df['snap_dist_m'].max():.1f}m)")

print(f"[Step 3 完成, 耗时 {time.time()-t2:.1f}s]")

# ============================================================
# Step 4: 网络距离计算 (优化策略)
# ============================================================
print("\n[Step 4] 计算网络可达性")
print("-" * 50)
print(f"搜索半径: {MAX_DIST_M:.0f}m ({MAX_TIME_MIN}分钟步行)")
print(f"OD矩阵: {len(comm_df)} × {len(poi_df):,} = {len(comm_df)*len(poi_df):,}")
t3 = time.time()

# 策略: 使用优化的NetworkX最短路径
# 预计算: 建立节点->POI的映射
node_to_poi_idx = defaultdict(list)
for poi_i, nid in enumerate(poi_df['nearest_node'].values):
    node_to_poi_idx[nid].append(poi_i)

# 设施供给
poi_df['supply'] = 1.0
if 'supply' in poi_df.columns:
    poi_df['supply'] = pd.to_numeric(poi_df['supply'], errors='coerce').fillna(1.0)
facility_supply = poi_df['supply'].values

# 日间和夜间设施
day_mask = np.ones(len(poi_df), dtype=bool)
night_mask = poi_df['night_service_final'].astype(bool).values

# 计算每个小区的网络可达性
# 优化: 使用多源BFS/dijkstra
comm_nodes = comm_df['nearest_node'].values
poi_nodes = poi_df['nearest_node'].values

# 设施节点列表
all_poi_nodes_unique = sorted(set(poi_nodes))
node_to_poi_count = defaultdict(int)
for nid in poi_nodes:
    node_to_poi_count[nid] += 1

# 创建设施服务能力图 (设施节点 -> 服务供给)
# Step1: 计算每个设施节点的 R_j = S_j / sum(P_i) for i in catchment
# 先计算设施吸引范围(1250m内的人口)

print("计算设施吸引力 R_j...")
# Dijkstra: 从每个POI节点反向搜索
# R_j = S_j / sum(Population within 1250m)
# 这里用简化: R_j = S_j / (人口总和 * 比例)

# 创建设施供给权重
R_j = facility_supply.copy()  # 简化为1
fac_df = poi_df[['supply', 'night_service_final']].copy()
fac_df['R_j'] = R_j

# Step1: 计算每个设施的服务能力 (基于周围人口)
# 对于每个设施节点, 找1250m内的小区人口
print("计算设施周围人口...")
fac_nodes_set = set(poi_nodes)
G_main_undirected = G_main.to_undirected() if G_main.is_directed() else G_main

# 找每个设施节点的可达小区 (1250m内)
# 优化: 只对有设施的节点做Dijkstra
facility_pop_reach = np.zeros(len(poi_df))
facility_pop_reach_night = np.zeros(len(poi_df))

# 预计算: 小区节点到人口的映射
comm_pop_dict = {}
for i, (nid, pop) in enumerate(zip(comm_nodes, comm_df['population_est'].fillna(comm_df['population']).values)):
    if nid in G_main_undirected:
        comm_pop_dict[nid] = (i, pop)

# 从设施节点Dijkstra
import heapq

def dijkstra_reachable_sum(start_node, max_dist, G, node_pop_map):
    """Dijkstra返回可达人口总和"""
    if start_node not in G:
        return 0.0
    dist = {start_node: 0.0}
    pq = [(0.0, start_node)]
    total_pop = 0.0
    nodes_visited = 0
    max_visits = 5000  # 限制搜索节点数

    while pq:
        d, node = heapq.heappop(pq)
        if nodes_visited > max_visits:
            break
        if d > max_dist:
            break
        if d > dist.get(node, float('inf')):
            continue
        nodes_visited += 1

        if node in node_pop_map:
            total_pop += node_pop_map[node][1]

        for neighbor in G.neighbors(node):
            edge_data = G[node][neighbor]
            edge_len = edge_data.get('length', 10.0)
            nd = d + edge_len
            if nd < dist.get(neighbor, float('inf')) and nd <= max_dist:
                dist[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))

    return total_pop

print("计算日间设施吸引力...")
# 日间: 对所有设施节点计算
fac_nodes_unique = sorted(set(poi_nodes))
day_pop_reach = np.zeros(len(fac_nodes_unique))
day_R_j = np.zeros(len(fac_nodes_unique))

for fi, fnode in enumerate(fac_nodes_unique):
    pop_reach = dijkstra_reachable_sum(fnode, MAX_DIST_M, G_main_undirected, comm_pop_dict)
    day_pop_reach[fi] = pop_reach
    # R_j = S_j / P_reach
    if pop_reach > 0:
        day_R_j[fi] = facility_supply[list(poi_nodes).index(fnode)] / pop_reach

print("计算夜间设施吸引力...")
night_poi_nodes = [poi_nodes[i] for i in range(len(poi_nodes)) if night_mask[i]]
night_fac_unique = sorted(set(night_poi_nodes))
night_pop_reach = np.zeros(len(night_fac_unique))
night_R_j = np.zeros(len(night_fac_unique))

for fi, fnode in enumerate(night_fac_unique):
    pop_reach = dijkstra_reachable_sum(fnode, MAX_DIST_M, G_main_undirected, comm_pop_dict)
    night_pop_reach[fi] = pop_reach
    if pop_reach > 0:
        idx = list(poi_nodes).index(fnode)
        night_R_j[fi] = facility_supply[idx] / pop_reach

print(f"日间可达设施节点: {len(day_R_j)}")
print(f"夜间可达设施节点: {len(night_R_j)}")

# Step2: 计算每个小区的可达性
print("\n计算小区可达性 A_i...")

# 小区节点到设施节点映射
comm_to_fac = defaultdict(list)
for poi_i, fnode in enumerate(poi_nodes):
    comm_to_fac[fnode].append(poi_i)

def compute_accessibility(comm_nid, fac_R_j_map, G_net, max_dist, supply_vals, poi_node_list):
    """计算单个小区的可达性"""
    if comm_nid not in G_net:
        return 0.0

    # Dijkstra到所有可达设施
    dist_map = {comm_nid: 0.0}
    pq = [(0.0, comm_nid)]
    accessibility = 0.0
    nodes_visited = 0
    max_visits = 5000

    while pq:
        d, node = heapq.heappop(pq)
        if nodes_visited > max_visits:
            break
        if d > max_dist:
            break
        if d > dist_map.get(node, float('inf')):
            continue
        nodes_visited += 1

        # 检查该节点是否有设施
        if node in fac_R_j_map:
            for fac_i in fac_R_j_map[node]:
                accessibility += fac_R_j_map[node][fac_i]

        for neighbor in G_net.neighbors(node):
            edge_data = G_net[node][neighbor]
            edge_len = edge_data.get('length', 10.0)
            nd = d + edge_len
            if nd < dist_map.get(neighbor, float('inf')) and nd <= max_dist:
                dist_map[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))

    return accessibility

# 建立: node -> {fac_idx: R_j} 映射
node_day_R = defaultdict(dict)
for fi, fnode in enumerate(fac_nodes_unique):
    if day_R_j[fi] > 0:
        # 该节点上的所有设施
        for poi_i in comm_to_fac.get(fnode, []):
            node_day_R[fnode][poi_i] = day_R_j[fi]

node_night_R = defaultdict(dict)
for fi, fnode in enumerate(night_fac_unique):
    if night_R_j[fi] > 0:
        for poi_i in comm_to_fac.get(fnode, []):
            if night_mask[poi_i]:
                node_night_R[fnode][poi_i] = night_R_j[fi]

# 并行计算小区可达性
from concurrent.futures import ThreadPoolExecutor, as_completed
import math

print(f"计算 {len(comm_nodes)} 个小区的可达性...")

def calc_comm_accessibility(i):
    cnid = comm_nodes[i]
    a_day = compute_accessibility(cnid, node_day_R, G_main_undirected, MAX_DIST_M, facility_supply, poi_nodes)
    a_night = compute_accessibility(cnid, node_night_R, G_main_undirected, MAX_DIST_M, facility_supply, poi_nodes)
    return i, a_day, a_night

results_day = np.zeros(len(comm_df))
results_night = np.zeros(len(comm_df))

# 多线程
n_workers = min(8, os.cpu_count() or 4)
batch_size = math.ceil(len(comm_df) / n_workers)

with ThreadPoolExecutor(max_workers=n_workers) as executor:
    futures = {executor.submit(calc_comm_accessibility, i): i for i in range(len(comm_df))}
    done = 0
    for future in as_completed(futures):
        i, a_d, a_n = future.result()
        results_day[i] = a_d
        results_night[i] = a_n
        done += 1
        if done % 50 == 0:
            print(f"  进度: {done}/{len(comm_df)} ({100*done/len(comm_df):.0f}%)")

# 归一化
a_day_max = max(results_day.max(), 1e-9)
a_night_max = max(results_night.max(), 1e-9)
results_day_norm = results_day / a_day_max
results_night_norm = results_night / a_night_max

print(f"\n[Step 4 完成, 耗时 {time.time()-t3:.1f}s]")

# ============================================================
# Step 5: TPI + SAII 计算
# ============================================================
print("\n[Step 5] TPI + SAII 计算")
print("-" * 50)

# 组装结果
access_results = comm_df[['id', 'lng', 'lat', 'population_est']].copy()
access_results = access_results.rename(columns={
    'id': 'community_id',
    'population_est': 'population'
})
access_results['A_day_raw'] = results_day
access_results['A_night_raw'] = results_night
access_results['A_day_norm'] = results_day_norm
access_results['A_night_norm'] = results_night_norm

# TPI
day_vals = access_results['A_day_norm'].values
night_vals = access_results['A_night_norm'].values
access_results['TPI'] = np.where(day_vals > 0, (night_vals - day_vals) / day_vals * 100, 0.0)
access_results['accessibility_gap'] = day_vals - night_vals
access_results['accessibility_ratio'] = np.where(day_vals > 0, night_vals / day_vals, 0.0)

# SAII
SAI = access_results['A_day_norm']  # 标准化可达性指数
SAII = SAI * access_results['TPI'].abs() / 100
access_results['SAII'] = SAII

# TPI等级
def classify_tpi(tpi):
    if tpi >= 50: return '4-Severe'
    if tpi >= 20: return '3-Moderate'
    if tpi >= 5: return '2-Mild'
    if tpi >= -5: return '1-None'
    return '0-NightAdv'

access_results['TPI_level'] = access_results['TPI'].apply(classify_tpi)

# 保存
output_csv = os.path.join(BASE, "p7_network_accessibility_results.csv")
access_results.to_csv(output_csv, index=False, encoding='utf-8-sig')
print(f"[OK] 保存: {output_csv}")

# ============================================================
# 结果汇总
# ============================================================
print("\n" + "=" * 70)
print("P7 网络可达性分析结果")
print("=" * 70)
print(f"南山区小区: {len(access_results)}")
print(f"总人口: {access_results['population'].sum():,}")
print(f"POI: {len(poi_df):,} (日间), {night_mask.sum():,} (夜间)")
print(f"网络节点: {G_main.number_of_nodes():,}")
print(f"网络边: {G_main.number_of_edges():,}")
print(f"道路总长: {total_road_len/1000:.1f} km")
print(f"道路密度: {total_road_len/1000/187.53:.1f} km/km²")
print(f"搜索半径: {MAX_DIST_M:.0f}m (15分钟)")

print(f"\n日间可达性: mean={results_day_norm.mean():.4f}, median={np.median(results_day_norm):.4f}")
print(f"夜间可达性: mean={results_night_norm.mean():.4f}, median={np.median(results_night_norm):.4f}")

print(f"\nTPI (时间贫困指数):")
print(f"  mean={access_results['TPI'].mean():.1f}%, median={access_results['TPI'].median():.1f}%")
print(f"  min={access_results['TPI'].min():.1f}%, max={access_results['TPI'].max():.1f}%")

print("\nTPI Level分布:")
for level, cnt in access_results['TPI_level'].value_counts().sort_index().items():
    n_people = access_results[access_results['TPI_level']==level]['population'].sum()
    print(f"  {level}: {cnt:3d} ({100*cnt/len(access_results):.1f}%) 人口: {n_people:,}")

print("\nTop 10 时间贫困小区:")
cols = ['community_id', 'population', 'A_day_norm', 'A_night_norm', 'TPI', 'SAII']
print(access_results.nlargest(10, 'TPI')[cols].to_string(index=False))

print(f"\n总耗时: {time.time()-t0:.1f}s")
print("\n*** P7 COMPLETE ***")
