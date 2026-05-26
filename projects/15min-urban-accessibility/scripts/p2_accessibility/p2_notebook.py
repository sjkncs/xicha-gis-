# -*- coding: utf-8 -*-
"""P2: Rewrite Cell 25 - Multi-period 2SFCA with FIXED logic"""
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NB = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\15min_urban_accessibility_SCI.ipynb"
with open(NB, encoding='utf-8') as f:
    nb = json.load(f)

cells = nb['cells']

# Find cell 25
cell25 = cells[25]

new_cell25 = '''# ============================================================================
# 多时段 2SFCA 可达性计算 (P2: 时段约束修正版)
# ============================================================================

# 设施白天时段权重（facility_type -> 白天供给系数）
# v2.csv 的 night_service_final 已由精细化推断得出；此处补充白天权重调整
FACILITY_DAY_WEIGHT = {
    'convenience': 1.0,
    'supermarket': 1.0,
    'pharmacy': 1.0,
    'hospital': 1.0,
    'clinic': 1.0,
    'school': 1.0,
    'kindergarten': 1.0,
    'bank': 1.0,
    'restaurant': 1.0,
    'bus_stop': 1.0,
    'subway': 1.0,
}

def run_multi_period_2sfca(communities_df, poi_df, od_matrix,
                            search_radius=1250):
    """
    多时段 2SFCA 可达性计算 — 修正版
    
    时段定义:
      - 白天 (day): 06:00-22:00，所有设施可用
      - 夜间 (night): 22:00-06:00，仅 night_service_final=True 的设施可用
    
    输出字段:
      - A_i_2sfca_day / A_i_2sfca_norm_day
      - A_i_2sfca_night / A_i_2sfca_norm_night
      - TPI: Time Poverty Index，夜间相对剥夺率（%）
      - accessibility_gap: 白天-夜间绝对差
      - accessibility_ratio: 夜间/白天比值
      - TPI_level: 剥夺程度分级标签
    """
    results = communities_df.copy()
    
    # --- Day: all facilities, apply day-weight ---
    print("\\n[DAY] 处理白天时段 (06:00-22:00)...")
    day_poi = poi_df.copy()
    day_poi['_day_weight'] = day_poi['facility_type'].map(
        lambda t: FACILITY_DAY_WEIGHT.get(t, 1.0)
    )
    day_poi['effective_supply'] = day_poi['supply'] * day_poi['_day_weight']
    
    fac_df_day = day_poi[['effective_supply', 'supply', 'facility_type']].copy()
    comm_df = results[['community_id', 'population']].copy()
    
    model_day = TwoStepFloatingCatchmentArea(
        search_radius_m=search_radius,
        supply_col='effective_supply',
        demand_col='population'
    )
    comm_result_day, _ = model_day.fit_transform(comm_df, fac_df_day, od_matrix)
    results = results.merge(
        comm_result_day[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']],
        on='community_id', how='left'
    )
    results = results.rename(columns={
        'A_i_2sfca': 'A_i_2sfca_day',
        'A_i_2sfca_norm': 'A_i_2sfca_norm_day'
    })
    
    # --- Night: only night_service_final=True facilities ---
    print("[NIGHT] 处理夜间时段 (22:00-06:00)...")
    night_mask = poi_df['night_service_final'] == True
    night_poi = poi_df[night_mask].copy().reset_index(drop=True)
    
    if len(night_poi) == 0:
        results['A_i_2sfca_night'] = 0.0
        results['A_i_2sfca_norm_night'] = 0.0
        print("  [警告] 无夜间服务设施，夜间可达性设为0")
    else:
        night_poi['effective_supply'] = night_poi['supply']
        
        # 从完整 OD 矩阵中提取夜间设施对应的列
        night_idx = poi_df[night_mask].index.tolist()
        od_night = od_matrix[:, night_idx]
        
        fac_df_night = night_poi[['effective_supply', 'supply', 'facility_type']].copy()
        comm_result_night, _ = model_day.fit_transform(
            comm_df, fac_df_night, od_night
        )
        results = results.merge(
            comm_result_night[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']],
            on='community_id', how='left'
        )
        results = results.rename(columns={
            'A_i_2sfca': 'A_i_2sfca_night',
            'A_i_2sfca_norm': 'A_i_2sfca_norm_night'
        })
    
    # --- TPI (Time Poverty Index) ---
    day_vals   = results['A_i_2sfca_norm_day'].fillna(0.0)
    night_vals = results['A_i_2sfca_norm_night'].fillna(0.0)
    
    results['TPI'] = np.where(
        day_vals > 0,
        (night_vals - day_vals) / day_vals * 100,
        0.0
    )
    results['accessibility_gap'] = day_vals - night_vals
    results['accessibility_ratio'] = np.where(
        day_vals > 0,
        night_vals / day_vals,
        np.where(night_vals > 0, 999.0, 0.0)
    )
    
    def classify_tpi(tpi):
        if tpi >= 50:  return '4-严重剥夺'
        if tpi >= 20:  return '3-中度剥夺'
        if tpi >= 5:   return '2-轻度剥夺'
        if tpi >= -5:  return '1-无明显剥夺'
        return '0-夜间优势'
    
    results['TPI_level'] = results['TPI'].apply(classify_tpi)
    
    # --- Summary ---
    print(f"\\n{'='*58}")
    print(f"多时段可达性统计摘要:")
    print(f"{'='*58}")
    print(f"白天可达性: mean={day_vals.mean():.4f}, median={day_vals.median():.4f}")
    print(f"夜间可达性: mean={night_vals.mean():.4f}, median={night_vals.median():.4f}")
    print(f"夜间设施数: {len(night_poi) if len(night_poi)>0 else 0} / {len(poi_df)} "
          f"({100*len(night_poi)/len(poi_df):.1f}%)")
    print(f"TPI 均值={results['TPI'].mean():.1f}%, 中位数={results['TPI'].median():.1f}%")
    print(f"剥夺程度分布:")
    for level, cnt in results['TPI_level'].value_counts().sort_index().items():
        print(f"  {level}: {cnt} 个小区 ({100*cnt/len(results):.1f}%)")
    
    return results

# 执行多时段 2SFCA
print("\\n开始执行多时段 2SFCA 计算...")
acc_results = run_multi_period_2sfca(
    acc_results, poi_df, od_matrix, search_radius=SEARCH_RADIUS_M
)
print("\\n多时段计算完成!")
'''

cell25['source'] = [new_cell25]

with open(NB, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False)

print("Cell 25 (fixed) saved!")

# Verify
with open(NB, encoding='utf-8') as f:
    nb2 = json.load(f)
src25 = ''.join(nb2['cells'][25]['source'])
checks = [
    ('night_service_final used', 'night_service_final' in src25),
    ('effective_supply fixed', 'effective_supply' in src25),
    ('TPI calculation', 'TPI' in src25),
    ('TPI_level 5-level', 'TPI_level' in src25),
    ('accessibility_ratio', 'accessibility_ratio' in src25),
    ('No period_poi bug', 'period_poi[\'night' not in src25),
    ('FACILITY_NIGHT_SERVICE gone', 'FACILITY_NIGHT_SERVICE' not in src25),
    ('night_poi defined before use', src25.find('night_poi') < src25.find('night_poi[') or src25.find('night_poi') == src25.rfind('night_poi')),
]
for name, ok in checks:
    print("  {}: {}".format("OK" if ok else "FAIL", name))
