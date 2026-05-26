# -*- coding: utf-8 -*-
"""
批量修复 notebook 中的关键问题:
1. Cell 19: 移除随机覆盖 supply 的代码（改用已有的 supply）
2. Cell 21: TwoStepFloatingCatchmentArea 向量化优化
"""

import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

nb_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(nb_path, encoding='utf-8') as f:
    nb = json.load(f)

# ─────────────────────────────────────────────
# Fix 1: Cell 19 — 移除 supply 随机覆盖代码
# ─────────────────────────────────────────────
cell19_idx = None
cell21_idx = None
for ci, cell in enumerate(nb['cells']):
    if cell['cell_type'] != 'code':
        continue
    src = ''.join(cell.get('source', []))
    if 'class TwoStepFloatingCatchmentArea' in src:
        cell21_idx = ci
    if '# 为设施分配供给权重' in src and 'generate_supplementary_poi' in src:
        cell19_idx = ci

print(f"Cell 19 index: {cell19_idx}, Cell 21 index: {cell21_idx}")

if cell19_idx is not None:
    old_src = nb['cells'][cell19_idx]['source']
    # 找到并替换 supply 随机生成那段代码
    old_text = old_src
    new_text = old_text.replace(
        "    if 'supply' not in poi_df.columns or poi_df['supply'].isna().all():\n        poi_df['supply'] = 1.0  # fallback\n        print('[NOTE] supply 使用默认值 1.0')\n    else:\n        poi_df['supply'] = poi_df['supply'].fillna(1.0)\n    poi_df['supply'] = np.random.uniform(0.5, 1.0, size=len(poi_df))  # 模拟评分归一化\n",
        "    if 'supply' not in poi_df.columns or poi_df['supply'].isna().all():\n        poi_df['supply'] = 1.0  # fallback\n        print('[NOTE] supply 使用默认值 1.0')\n    else:\n        poi_df['supply'] = poi_df['supply'].fillna(1.0)\n    # 【重要】不覆盖已从 nanshan_poi_integrated.csv 推导的 supply\n"
    )
    # 如果上面没匹配到，尝试另一种格式
    if old_text == new_text:
        new_text = old_text.replace(
            "    poi_df['supply'] = np.random.uniform(0.5, 1.0, size=len(poi_df))  # 模拟评分归一化\n",
            "    # 【重要】不覆盖已从 nanshan_poi_integrated.csv 推导的 supply\n"
        )
    # 如果还有问题，直接找包含随机 supply 的行替换
    if old_text == new_text:
        lines = old_text.split('\n')
        new_lines = []
        skip_next = False
        for li, line in enumerate(lines):
            if 'np.random.uniform(0.5, 1.0, size=len(poi_df))' in line:
                new_lines.append("    # 【重要】保留已推导的 supply（不随机覆盖）")
                skip_next = False
            elif '随机覆盖' in line or skip_next:
                skip_next = False
            else:
                new_lines.append(line)
        new_text = '\n'.join(new_lines)
    
    nb['cells'][cell19_idx]['source'] = new_text
    print(f"Cell {cell19_idx} supply fix: {'OK' if old_text != new_text else 'NO CHANGE (check)'}")
else:
    print("ERROR: Cell 19 not found!")

# ─────────────────────────────────────────────
# Fix 2: Cell 21 — 向量化 TwoStepFloatingCatchmentArea
# ─────────────────────────────────────────────
new_cell21 = '''# ============================================================================
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
        demand = facilities_df[self.demand_col].values.astype(np.float64) \
            if self.demand_col in facilities_df.columns \
            else np.ones(od_matrix.shape[0])  # 如果没有人口数据，假设等权重
        
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
'''

if cell21_idx is not None:
    nb['cells'][cell21_idx]['source'] = new_cell21
    print(f"Cell {cell21_idx} (TwoStepFloatingCatchmentArea) vectorized ✓")
else:
    print("ERROR: Cell 21 not found!")

# 保存
with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False)
print("\nNotebook saved!")
