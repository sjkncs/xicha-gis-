# -*- coding: utf-8 -*-
"""
优化 Cell 18 (NetworkDistanceCalculator) 和 Cell 23 (Gaussian2SFCA)
1. OD Matrix: 移除 iterrows，用预计算的最近节点列表
2. Gaussian 2SFCA: 全矩阵向量化，替换所有双循环
"""

import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# ─────────────────────────────────────────────
# 新的 Cell 18: 优化版 NetworkDistanceCalculator
# ─────────────────────────────────────────────
new_cell18 = '''# ============================================================================
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
'''

# ─────────────────────────────────────────────
# 新的 Cell 23: 优化版 Gaussian2SFCA（向量化）
# ─────────────────────────────────────────────
new_cell23 = '''# ============================================================================
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

print("\\n" + "=" * 60)
print("Gaussian 2SFCA 结果摘要")
print("=" * 60)
g_vals = acc_results['A_i_gaussian_norm']
print(f"标准化可达性: mean={g_vals.mean():.4f}, median={g_vals.median():.4f}, std={g_vals.std():.4f}")
print(f"低可达性(<0.2)小区: {(g_vals < 0.2).sum()} 个 ({(g_vals < 0.2).mean()*100:.1f}%)")
print(f"高可达性(>0.8)小区: {(g_vals > 0.8).sum()} 个 ({(g_vals > 0.8).mean()*100:.1f}%)")
'''

# 查找 cell 索引
cell18_idx = None
cell23_idx = None
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'class NetworkDistanceCalculator' in src:
        cell18_idx = ci
    if 'class Gaussian2SFCA' in src:
        cell23_idx = ci

print(f"Cell 18 index: {cell18_idx}")
print(f"Cell 23 index: {cell23_idx}")

if cell18_idx is not None:
    nb['cells'][cell18_idx]['source'] = new_cell18
    print(f"Cell {cell18_idx} (NetworkDistanceCalculator) updated ✓")
else:
    print("ERROR: Cell 18 not found!")

if cell23_idx is not None:
    nb['cells'][cell23_idx]['source'] = new_cell23
    print(f"Cell {cell23_idx} (Gaussian2SFCA) updated ✓")
else:
    print("ERROR: Cell 23 not found!")

# 保存
with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False)

print("\nNotebook saved!")
