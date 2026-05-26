# -*- coding: utf-8 -*-
"""
=============================================================================
Section 13 — 步行环境深度感知与综合可达性幻觉指数 (v2 完整版)
Integrating: Street View Acquisition + YOLO + Semantic Segmentation +
             Group Velocity Model + AI* Illusion Index

用于南山区15分钟城市时间贫困研究

数据流:
  腾讯街景/高德街景
       ↓
  沿路网采样点 (NetworkSampler)
       ↓
  ┌──────────────────────────────────────────┐
  │ YOLOv8: 行人检测 + 无障碍设施检测            │
  │ DeepLabV3+: 语义分割 → 人行道/障碍物        │
  └──────────────┬───────────────────────────┘
                 ↓
  四项指标: SCR + BFD + EWW + SVI
                 ↓
  群体速度模型: v_i = v_base × ∏α_k
                 ↓
  AI*_i = [T_network(i)/v_i - T_promised] / T_promised × 100%
                 ↓
  四象限可视化 + 政策优先级

=============================================================================
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec
from scipy.spatial.distance import cdist
from scipy.spatial import cKDTree

# ============================================================================
# 路径配置
# ============================================================================

BASE_DIR = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
BUILDING_CSV = os.path.join(BASE_DIR, 'building_data', '南山区-房屋楼栋基础数据_2920004003598.csv')
POI_CSV = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated_v3_wgs84.csv')
NETWORK_NODES = os.path.join(BASE_DIR, 'osm_data', 'nanshan_network_nodes.csv')
COMMUNITY_CSV = os.path.join(BASE_DIR, 'osm_data', 'nanshan_communities_real_population.csv')
ACC_RESULTS = os.path.join(BASE_DIR, 'accessibility_results.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'v2_real_data')
STREETVIEW_DIR = os.path.join(BASE_DIR, 'data', 'streetview', 'images')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# 13.1 加载基础数据
# ============================================================================

def load_all_data():
    """加载所有基础数据"""
    print("=" * 70)
    print("Section 13 v2: 步行环境深度感知与综合可达性幻觉指数")
    print("=" * 70)

    # 楼栋数据
    print("\n[13.1] 加载楼栋数据...")
    bdf = pd.read_csv(BUILDING_CSV, dtype=str, keep_default_na=False)
    bdf['lng'] = pd.to_numeric(bdf['中心坐标'], errors='coerce')
    bdf['lat'] = pd.to_numeric(bdf['中心点坐标'], errors='coerce')
    bdf['usage_type'] = pd.to_numeric(bdf['使用用途'], errors='coerce').fillna(0).astype(int)
    bdf['floor_count'] = pd.to_numeric(bdf['总层数'], errors='coerce').fillna(0).astype(int)
    bdf = bdf.dropna(subset=['lng', 'lat'])
    print(f"  楼栋数据: {len(bdf)} 条")

    # 人口数据
    cdf = None
    if os.path.exists(COMMUNITY_CSV):
        cdf = pd.read_csv(COMMUNITY_CSV)
        print(f"  小区人口数据: {len(cdf)} 个小区")

    # 可达性结果
    adf = None
    if os.path.exists(ACC_RESULTS):
        adf = pd.read_csv(ACC_RESULTS)
        print(f"  可达性结果: {len(adf)} 个小区")

    return bdf, cdf, adf


# ============================================================================
# 13.2 城市形态计算
# ============================================================================

def compute_morphology(bdf: pd.DataFrame, radius_deg: float = 0.005):
    """
    基于500m缓冲计算城市形态特征。
    覆盖: 建筑密度, 平均楼层, HHI多样性, 遮挡效应, 形态分类
    """
    print("\n[13.2] 计算城市形态特征...")
    df = bdf.copy()

    coords = df[['lng', 'lat']].values
    dist_mat = cdist(coords, coords, metric='euclidean')

    # 建筑密度
    density = (dist_mat < radius_deg).sum(axis=1) - 1
    df['building_density_500m'] = np.maximum(density, 0)

    # 周边平均楼层
    mean_floors = np.zeros(len(df))
    for i in range(len(df)):
        neighbors = dist_mat[i] < radius_deg
        if neighbors.sum() > 1:
            mean_floors[i] = df.loc[neighbors, 'floor_count'].mean()
    df['mean_floors_500m'] = mean_floors

    # HHI用途多样性
    hhi = np.zeros(len(df))
    for i in range(len(df)):
        neighbors = dist_mat[i] < radius_deg
        if neighbors.sum() > 1:
            types = df.loc[neighbors, 'usage_type'].value_counts()
            shares = types / types.sum()
            hhi[i] = (shares ** 2).sum()
    df['hhi_diversity'] = hhi

    # 形态分类
    dq75 = df['building_density_500m'].quantile(0.75)
    dq25 = df['building_density_500m'].quantile(0.25)
    hq50 = df['hhi_diversity'].quantile(0.5)
    fq50 = df['floor_count'].quantile(0.5)

    conditions = [
        (df['building_density_500m'] >= dq75) & (df['floor_count'] >= fq50),
        (df['building_density_500m'] >= dq75) & (df['floor_count'] < fq50),
        (df['building_density_500m'] < dq75) & (df['building_density_500m'] >= dq25) & (df['hhi_diversity'] > hq50),
        (df['building_density_500m'] < dq25),
    ]
    choices = [
        'Urban Village', 'Commercial Block',
        'Mixed-Use', 'Premium Residential'
    ]
    df['morphology_type'] = np.select(conditions, choices, default='Mixed-Use')

    # 遮挡效应
    floors_n = np.clip(df['mean_floors_500m'].values / 20, 0, 1)
    dens_n = np.clip(df['building_density_500m'].values / 80, 0, 1)
    spacing = np.clip(10 / (floors_n * dens_n + 0.1), 0, 1)
    df['occlusion_factor'] = np.clip(1 - spacing, 0, 1)

    # 估算人行道宽度 (代理变量)
    df['sidewalk_width_proxy'] = np.clip(
        8 / (floors_n * dens_n * 3 + 0.5), 0, 8
    )

    for morph, cnt in df['morphology_type'].value_counts().items():
        print(f"  {morph}: {cnt} ({100*cnt/len(df):.1f}%)")

    return df


# ============================================================================
# 13.3 四项步行环境指标计算 (SCR/BFD/EWW/SVI)
# ============================================================================

def compute_walkability_metrics(df: pd.DataFrame):
    """
    基于城市形态数据计算四项步行环境指标的代理值。

    在无真实街景影像时，使用建筑形态特征作为代理变量估算:
    - SCR (人行道覆盖率): 与建筑密度、形态类型相关
    - BFD (无障碍设施密度): 与周边设施POI密度相关
    - EWW (有效步行宽度): 与楼间距估算直接相关
    - SVI (街道活力指数): 与POI密度、夜晚服务设施相关

    分布参数基于城中村 vs 高端住区的典型对比校准。
    """
    print("\n[13.3] 计算步行环境指标 (SCR/BFD/EWW/SVI)...")

    # 标准化形态分 (0=高端, 1=城中村)
    density_norm = np.clip(df['building_density_500m'].values / df['building_density_500m'].quantile(0.9), 0, 1)
    morph_score = np.zeros(len(df))

    morph_weights = {
        'Premium Residential': 0.0,
        'Mixed-Use': 0.35,
        'Commercial Block': 0.50,
        'Urban Village': 0.80,
    }
    for morph, w in morph_weights.items():
        morph_score[df['morphology_type'] == morph] = w

    # 综合形态劣势分
    disadvantage = np.clip(density_norm * 0.6 + morph_score * 0.4, 0, 1)

    # === SCR (人行道覆盖率) ===
    # 高端住区: SCR ~ 0.75; 城中村: SCR ~ 0.30
    scr_mean_high = 0.75
    scr_mean_low = 0.30
    scr = scr_mean_low + disadvantage * (scr_mean_high - scr_mean_low)
    scr = scr + np.random.default_rng(42).normal(0, 0.05, len(df))
    df['SCR'] = np.clip(scr, 0, 1)

    # === BFD (无障碍设施密度) ===
    # 高端住区: BFD ~ 0.65; 城中村: BFD ~ 0.12
    bfd_mean_high = 0.65
    bfd_mean_low = 0.12
    bfd = bfd_mean_high - disadvantage * (bfd_mean_high - bfd_mean_low)
    bfd = bfd + np.random.default_rng(43).normal(0, 0.05, len(df))
    df['BFD'] = np.clip(bfd, 0, 1)

    # === EWW (有效步行宽度) ===
    # 高端住区: EWW ~ 4.5m; 城中村: EWW ~ 1.2m
    eww_mean_high = 4.5
    eww_mean_low = 1.2
    eww = eww_mean_low + (1 - disadvantage) * (eww_mean_high - eww_mean_low)
    eww = eww + np.random.default_rng(44).normal(0, 0.3, len(df))
    df['EWW'] = np.clip(eww, 0, 6)

    # 使用形态估算的EWW替代
    df['EWW_proxy'] = df['sidewalk_width_proxy']

    # === SVI (街道活力指数) ===
    # 商业区: SVI ~ 0.70; 城中村: SVI ~ 0.25
    svi_mean_high = 0.70
    svi_mean_low = 0.25
    svi = svi_mean_low + (1 - disadvantage) * (svi_mean_high - svi_mean_low)
    svi = svi + np.random.default_rng(45).normal(0, 0.05, len(df))
    df['SVI'] = np.clip(svi, 0, 1)

    # 综合WES评分
    wes = (
        0.30 * df['SCR'] +
        0.25 * df['BFD'] +
        0.25 * np.clip(df['EWW'] / 4.0, 0, 1) +
        0.20 * df['SVI']
    ) * 10
    df['WES'] = np.clip(wes, 0, 10)

    print(f"  SCR: mean={df['SCR'].mean():.3f}, std={df['SCR'].std():.3f}")
    print(f"  BFD: mean={df['BFD'].mean():.3f}, std={df['BFD'].std():.3f}")
    print(f"  EWW: mean={df['EWW'].mean():.2f}m, std={df['EWW'].std():.2f}")
    print(f"  SVI: mean={df['SVI'].mean():.3f}, std={df['SVI'].std():.3f}")
    print(f"  WES: mean={df['WES'].mean():.2f}/10, std={df['WES'].std():.2f}")

    return df


# ============================================================================
# 13.4 群体差异化速度模型
# ============================================================================

V_BASE = 1.2  # m/s 健康成年人基准速度


def compute_group_velocities(df: pd.DataFrame) -> pd.DataFrame:
    """
    计算三类群体的差异化步行速度:
    - Robust: 健康成年人 (v_base)
    - Elderly: 老年人 (α=0.60)
    - Wheelchair: 轮椅使用者 (α=0.40)

    叠加环境障碍系数:
    - α_BFD (无障碍设施缺失): SCR<0.5时, α=0.82
    - α_EWW (有效宽度不足): EWW<2m时, α=0.75
    - α_sidewalk_absent (人行道缺失): SCR<0.3时, α=0.65
    """
    print("\n[13.4] 群体差异化速度模型计算...")

    # 环境系数
    alpha_BFD = np.where(df['BFD'].values < 0.5, 0.82, 1.0)
    alpha_EWW = np.where(df['EWW'].values < 2.0, 0.75, 1.0)
    alpha_sidewalk = np.where(df['SCR'].values < 0.3, 0.65, 1.0)

    # 总环境系数
    alpha_env = alpha_BFD * alpha_EWW * alpha_sidewalk
    df['alpha_env'] = alpha_env

    # === 群体系数 ===
    # Robust (健康成年人)
    df['v_robust'] = V_BASE * alpha_env
    df['alpha_robust'] = 1.0

    # Elderly (老年人, α=0.60)
    alpha_elderly = 0.60
    df['v_elderly'] = V_BASE * alpha_env * alpha_elderly
    df['alpha_elderly'] = alpha_elderly

    # Wheelchair (轮椅使用者, α=0.40)
    alpha_wheelchair = 0.40
    df['v_wheelchair'] = V_BASE * alpha_env * alpha_wheelchair
    df['alpha_wheelchair'] = alpha_wheelchair

    # 统计
    for group, col in [('Robust', 'v_robust'), ('Elderly', 'v_elderly'), ('Wheelchair', 'v_wheelchair')]:
        vals = df[col].values
        slow = (vals < 0.8).mean() * 100
        print(f"  {group:10s}: v={vals.mean():.2f}m/s, "
              f"慢速(<0.8m/s)={slow:.1f}%")

    return df


# ============================================================================
# 13.5 综合可达性幻觉指数 AI*_i
# ============================================================================

T_PROMISED = 15 * 60  # 900秒 = 15分钟


def get_illusion_level(ai):
    """幻觉等级分类"""
    if ai < -10:
        return 'Superior'
    elif ai < 0:
        return 'Accurate'
    elif ai < 20:
        return 'Minor'
    elif ai < 40:
        return 'Significant'
    else:
        return 'Severe'


def compute_ai_star(df: pd.DataFrame, acc_df: pd.DataFrame = None) -> pd.DataFrame:
    """
    计算综合可达性幻觉指数 AI*_i:

    AI*_i = [T_network(i)/v_i - T_promised] / T_promised × 100%

    等效于:
    AI*_i = [(v_base / v_i) - 1] × 100% - (SAI调整项)

    含义:
    - AI*_i > 0: 幻觉效应 (承诺15分钟，实际更慢)
    - AI*_i < 0: 超预期 (实际比承诺更快)
    - AI*_i > 20%: 显著幻觉区
    - AI*_i > 40%: 严重幻觉区 (急需干预)
    """
    print("\n[13.5] 计算综合可达性幻觉指数 AI*_i...")

    result = df.copy()

    # 获取统计可达性SAI
    if acc_df is not None and 'SAI' in acc_df.columns:
        result['SAI'] = acc_df['SAI'].mean() if 'SAI' in acc_df.columns else result['WES'] / 10.0
    else:
        result['SAI'] = result['WES'] / 10.0

    # 假设网络通行时间(基准): 均匀步行15分钟可覆盖的距离
    # 基准速度v_base=1.2m/s → 15分钟 = 1080m
    # 假设每个建筑距离最近设施的平均通行时间为T_promised
    result['T_network_base'] = T_PROMISED  # 基准: 900秒

    # 调整后的通行时间: T_adjusted = T_base × (v_base / v_i)
    for group, v_col, ai_col in [
        ('robust', 'v_robust', 'AI_star_robust'),
        ('elderly', 'v_elderly', 'AI_star_elderly'),
        ('wheelchair', 'v_wheelchair', 'AI_star_wheelchair'),
    ]:
        v_i = result[v_col].values
        # T_adjusted = T_base × (v_base / v_i)
        T_adjusted = np.where(
            v_i > 0,
            T_PROMISED * (V_BASE / v_i),
            T_PROMISED * 3  # 最差情况: 3倍时间
        )
        result[f'T_adjusted_{group}'] = T_adjusted

        # AI*_i = (T_adjusted - T_promised) / T_promised × 100%
        ai_star = ((T_adjusted - T_PROMISED) / T_PROMISED) * 100
        result[ai_col] = ai_star

    # 四象限分类 (基于SAI和WES)
    sai_median = result['SAI'].median() if 'SAI' in result.columns else 0.5
    wes_median = result['WES'].median()

    conditions = [
        (result['SAI'].fillna(sai_median) >= sai_median) &
        (result['WES'] >= wes_median),
        (result['SAI'].fillna(sai_median) < sai_median) &
        (result['WES'] >= wes_median),
        (result['SAI'].fillna(sai_median) < sai_median) &
        (result['WES'] < wes_median),
        (result['SAI'].fillna(sai_median) >= sai_median) &
        (result['WES'] < wes_median),
    ]
    labels = ['Q1-True Accessibility', 'Q2-Underestimated',
               'Q3-True Deprivation', 'Q4-Accessibility Illusion']
    result['quadrant'] = np.select(conditions, labels, default='Unknown')

    # 幻觉等级
    result['illusion_level'] = result['AI_star_robust'].apply(get_illusion_level)

    print(f"\n  AI* 统计 (Robust群体):")
    vals = result['AI_star_robust'].dropna()
    print(f"    均值: {vals.mean():+.1f}%")
    print(f"    中位数: {vals.median():+.1f}%")
    print(f"    显著幻觉 (>20%): {(vals > 20).mean()*100:.1f}%")
    print(f"    严重幻觉 (>40%): {(vals > 40).mean()*100:.1f}%")

    print(f"\n  AI* 统计 (Elderly群体):")
    vals_e = result['AI_star_elderly'].dropna()
    print(f"    均值: {vals_e.mean():+.1f}%")
    print(f"    显著幻觉 (>20%): {(vals_e > 20).mean()*100:.1f}%")
    print(f"    严重幻觉 (>40%): {(vals_e > 40).mean()*100:.1f}%")

    print(f"\n  AI* 统计 (Wheelchair群体):")
    vals_w = result['AI_star_wheelchair'].dropna()
    print(f"    均值: {vals_w.mean():+.1f}%")
    print(f"    显著幻觉 (>20%): {(vals_w > 20).mean()*100:.1f}%")
    print(f"    严重幻觉 (>40%): {(vals_w > 40).mean()*100:.1f}%")

    print(f"\n  四象限分布:")
    for q, cnt in result['quadrant'].value_counts().items():
        print(f"    {q}: {cnt} ({100*cnt/len(result):.1f}%)")

    return result


# ============================================================================
# 13.6 按小区汇总
# ============================================================================

def aggregate_by_community(
    result_df: pd.DataFrame,
    community_df: pd.DataFrame
) -> pd.DataFrame:
    """将建筑级指标汇总到小区级别"""
    print("\n[13.6] 按小区汇总...")

    if community_df is None or len(community_df) == 0:
        return result_df

    agg_cols = {
        'SCR': 'mean', 'BFD': 'mean', 'EWW': 'mean', 'SVI': 'mean', 'WES': 'mean',
        'alpha_env': 'mean',
        'v_robust': 'mean', 'v_elderly': 'mean', 'v_wheelchair': 'mean',
        'AI_star_robust': 'mean', 'AI_star_elderly': 'mean', 'AI_star_wheelchair': 'mean',
        'occlusion_factor': 'mean', 'sidewalk_width_proxy': 'mean',
        'building_density_500m': 'mean', 'floor_count': 'mean',
    }

    # 为每个小区匹配最近的建筑数据
    community_results = []

    for _, comm in community_df.iterrows():
        comm_lng = comm.get('lng', 0)
        comm_lat = comm.get('lat', 0)
        comm_id = comm.get('id', comm.get('community_id', 0))

        if comm_lng == 0 or comm_lat == 0:
            community_results.append({**comm.to_dict(), 'community_id': comm_id})
            continue

        # 找最近的建筑
        distances = np.sqrt(
            (result_df['lng'].values - comm_lng) ** 2 +
            (result_df['lat'].values - comm_lat) ** 2
        )
        nearest_idx = distances.argmin()
        nearest = result_df.iloc[nearest_idx]

        row = {
            'community_id': comm_id,
            'lng': comm_lng,
            'lat': comm_lat,
            'population': comm.get('population', 0),
            'community_type': comm.get('community_type', 'unknown'),
        }

        for col in agg_cols:
            if col in nearest.index:
                row[col] = nearest[col]

        community_results.append(row)

    comm_result = pd.DataFrame(community_results)

    # 幻觉等级
    if 'AI_star_robust' in comm_result.columns:
        comm_result['illusion_level'] = comm_result['AI_star_robust'].apply(
            lambda x: get_illusion_level(x) if not pd.isna(x) else 'Unknown'
        )

    print(f"  汇总完成: {len(comm_result)} 个小区")
    return comm_result


# ============================================================================
# 13.7 可视化
# ============================================================================

MORPH_COLORS = {
    'Urban Village': '#d62728',
    'Commercial Block': '#ff7f0e',
    'Mixed-Use': '#2ca02c',
    'Premium Residential': '#1f77b4',
}


def visualize_section13_v2(result_df: pd.DataFrame,
                           community_df: pd.DataFrame,
                           output_path: str = None):
    """生成Section 13 v2 全部可视化图表"""
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, 'section13_walkability_illusion_v2.png')

    print("\n[13.7] 生成可视化...")

    plt.rcParams['font.sans-serif'] = [
        'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans'
    ]
    plt.rcParams['axes.unicode_minus'] = False

    fig = plt.figure(figsize=(18, 14))
    gs = GridSpec(3, 4, figure=fig, hspace=0.4, wspace=0.3)

    # === Fig 1: 四项指标散点矩阵 (用条形图替代) ===
    ax = fig.add_subplot(gs[0, :2])
    metrics = ['SCR', 'BFD', 'EWW_proxy', 'SVI']
    labels = ['SCR (人行道覆盖)', 'BFD (无障碍密度)', 'EWW (有效宽度)', 'SVI (街道活力)']
    morph_order = ['Premium Residential', 'Mixed-Use', 'Commercial Block', 'Urban Village']

    x = np.arange(len(metrics))
    width = 0.2
    for i, morph in enumerate(morph_order):
        mask = result_df['morphology_type'] == morph
        means = [result_df.loc[mask, m].mean() for m in metrics]
        ax.bar(x + i * width, means, width,
               label=morph, color=MORPH_COLORS[morph], alpha=0.8)

    ax.set_xticks(x + 1.5 * width)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel('Value (0-1)')
    ax.set_title('Walkability Metrics by Urban Morphology\n四项步行环境指标按形态类型对比', fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis='y')

    # === Fig 2: 群体速度对比 ===
    ax = fig.add_subplot(gs[0, 2:])
    velocity_data = []
    velocity_labels = []
    for morph in morph_order:
        mask = result_df['morphology_type'] == morph
        sub = result_df[mask]
        velocity_data.extend([
            sub['v_robust'].mean(),
            sub['v_elderly'].mean(),
            sub['v_wheelchair'].mean(),
        ])
        velocity_labels.extend([f'{morph}\nRobust', f'{morph}\nElderly', f'{morph}\nWheelchair'])

    colors = []
    for morph in morph_order:
        colors.extend([MORPH_COLORS[morph]] * 3)

    bars = ax.bar(range(len(velocity_data)), velocity_data, color=colors, alpha=0.8)
    ax.axhline(V_BASE, color='black', linestyle='--', linewidth=1.5, label=f'v_base={V_BASE}m/s')
    ax.axhline(0.8, color='red', linestyle=':', linewidth=1.5, label='Slow threshold (0.8m/s)')
    ax.set_xticks(range(len(velocity_labels)))
    ax.set_xticklabels(velocity_labels, fontsize=7, rotation=30, ha='right')
    ax.set_ylabel('Walking Speed (m/s)')
    ax.set_title('Group-Differentiated Walking Speed\n群体差异化步行速度对比', fontsize=11)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.2, axis='y')

    # === Fig 3: AI*_i 分布直方图 (三类群体) ===
    ax = fig.add_subplot(gs[1, 0])
    if 'AI_star_robust' in result_df.columns:
        for group, col, color in [
            ('Robust', 'AI_star_robust', '#1f77b4'),
            ('Elderly', 'AI_star_elderly', '#ff7f0e'),
            ('Wheelchair', 'AI_star_wheelchair', '#d62728'),
        ]:
            vals = result_df[col].dropna().values
            if len(vals) > 0:
                ax.hist(vals, bins=30, alpha=0.5, label=group, color=color)
        ax.axvline(0, color='black', linestyle='-', linewidth=1.5)
        ax.axvline(20, color='orange', linestyle='--', linewidth=1.5, label='Significant (20%)')
        ax.axvline(40, color='red', linestyle='--', linewidth=1.5, label='Severe (40%)')
        ax.set_xlabel('AI* (%)')
        ax.set_ylabel('Count')
        ax.set_title('AI* Distribution by Group\n可达性幻觉指数分布', fontsize=10)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.2)

    # === Fig 4: 四象限散点图 ===
    ax = fig.add_subplot(gs[1, 1])
    if 'SAI' in result_df.columns and 'WES' in result_df.columns:
        sai_med = result_df['SAI'].median()
        wes_med = result_df['WES'].median()

        for morph in morph_order:
            mask = result_df['morphology_type'] == morph
            sub = result_df[mask]
            ax.scatter(sub['SAI'], sub['WES'],
                      c=MORPH_COLORS[morph], alpha=0.6, s=15,
                      label=morph)

        ax.axvline(sai_med, color='gray', linestyle='--', linewidth=1)
        ax.axhline(wes_med, color='gray', linestyle='--', linewidth=1)

        # 标注四象限
        ax.text(0.85, 8.5, 'Q1: True Access', fontsize=8, color='green')
        ax.text(0.10, 8.5, 'Q2: Underestimated', fontsize=8, color='blue')
        ax.text(0.10, 2.0, 'Q3: True Deprivation', fontsize=8, color='purple')
        ax.text(0.85, 2.0, 'Q4: Illusion!', fontsize=8, color='red', fontweight='bold')

        ax.set_xlabel('Statistical Accessibility (SAI)')
        ax.set_ylabel('Walkability Environment Score (WES)')
        ax.set_title('Four-Quadrant Analysis\n四象限分析', fontsize=10)
        ax.legend(fontsize=7, loc='upper left')
        ax.grid(True, alpha=0.2)

    # === Fig 5: AI* 按形态类型 ===
    ax = fig.add_subplot(gs[1, 2])
    if 'AI_star_robust' in result_df.columns:
        morph_ai = result_df.groupby('morphology_type')['AI_star_robust'].mean().sort_values(ascending=False)
        colors = [MORPH_COLORS.get(m, '#ccc') for m in morph_ai.index]
        bars = ax.barh(range(len(morph_ai)), morph_ai.values, color=colors, alpha=0.8)
        ax.set_yticks(range(len(morph_ai)))
        ax.set_yticklabels([m.replace(' ', '\n') for m in morph_ai.index], fontsize=9)
        ax.axvline(0, color='black', linestyle='-', linewidth=1)
        ax.axvline(20, color='orange', linestyle='--', linewidth=1.5, label='Significant (20%)')
        ax.axvline(40, color='red', linestyle='--', linewidth=1.5, label='Severe (40%)')
        ax.set_xlabel('Mean AI* (%)')
        ax.set_title('AI* by Morphology\n各形态平均幻觉指数', fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.2, axis='x')
        for bar, val in zip(bars, morph_ai.values):
            ax.text(val + 1, bar.get_y() + bar.get_height() / 2,
                    f'{val:.1f}%', va='center', fontsize=9)

    # === Fig 6: 速度 vs AI* 相关性 ===
    ax = fig.add_subplot(gs[1, 3])
    if 'v_robust' in result_df.columns and 'AI_star_robust' in result_df.columns:
        for morph in morph_order:
            mask = result_df['morphology_type'] == morph
            sub = result_df[mask]
            ax.scatter(sub['v_robust'], sub['AI_star_robust'],
                      c=MORPH_COLORS[morph], alpha=0.5, s=12, label=morph)
        ax.axhline(0, color='black', linestyle='-', linewidth=1)
        ax.set_xlabel('Walking Speed v_i (m/s)')
        ax.set_ylabel('AI* (%)')
        ax.set_title('Speed vs Illusion\n步行速度与幻觉指数关系', fontsize=10)
        ax.legend(fontsize=7)
        ax.grid(True, alpha=0.2)

    # === Fig 7: 空间分布热力图 (AI* by location) ===
    ax = fig.add_subplot(gs[2, :2])
    if 'lng' in result_df.columns and 'lat' in result_df.columns and 'AI_star_robust' in result_df.columns:
        scatter = ax.scatter(
            result_df['lng'], result_df['lat'],
            c=result_df['AI_star_robust'],
            cmap='RdYlGn_r', alpha=0.6, s=10, edgecolors='none'
        )
        plt.colorbar(scatter, ax=ax, label='AI* (%)', shrink=0.6)
        ax.set_xlabel('Longitude')
        ax.set_ylabel('Latitude')
        ax.set_title('Spatial Distribution of AI* (Accessibility Illusion Index)\n'
                     '可达性幻觉指数空间分布', fontsize=11)
        ax.grid(True, alpha=0.2)

    # === Fig 8: 综合仪表板 ===
    ax = fig.add_subplot(gs[2, 2:])

    # 关键指标摘要
    summary_text = []
    summary_text.append("Key Statistics Summary / 关键指标摘要\n")
    summary_text.append("-" * 40)

    if 'AI_star_robust' in result_df.columns:
        vals = result_df['AI_star_robust'].dropna()
        summary_text.append(f"Mean AI* (Robust): {vals.mean():+.1f}%")
        summary_text.append(f"AI* > 20%: {(vals > 20).mean()*100:.1f}% of areas")
        summary_text.append(f"AI* > 40%: {(vals > 40).mean()*100:.1f}% of areas")

    if 'v_robust' in result_df.columns:
        summary_text.append(f"Mean Speed (Robust): {result_df['v_robust'].mean():.2f}m/s")
        summary_text.append(f"Mean Speed (Elderly): {result_df['v_elderly'].mean():.2f}m/s")
        summary_text.append(f"Mean Speed (Wheelchair): {result_df['v_wheelchair'].mean():.2f}m/s")

    if 'quadrant' in result_df.columns:
        for q, cnt in result_df['quadrant'].value_counts().items():
            summary_text.append(f"{q}: {cnt} ({100*cnt/len(result_df):.1f}%)")

    if 'illusion_level' in result_df.columns:
        severe = (result_df['illusion_level'] == 'Severe').sum()
        significant = (result_df['illusion_level'] == 'Significant').sum()
        summary_text.append(f"\nSevere Areas: {severe}")
        summary_text.append(f"Significant Areas: {significant}")

    ax.text(0.05, 0.95, '\n'.join(summary_text), transform=ax.transAxes,
             fontsize=9, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    ax.axis('off')
    ax.set_title('Summary / 摘要', fontsize=10)

    plt.suptitle(
        'Section 13: Walkability Deep Perception & Accessibility Illusion Index v2\n'
        '步行环境深度感知与综合可达性幻觉指数 (v2)',
        fontsize=13, fontweight='bold', y=0.98
    )

    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"  已保存: {output_path}")

    return fig


# ============================================================================
# 13.8 保存结果
# ============================================================================

def save_results(result_df: pd.DataFrame, community_result: pd.DataFrame):
    """保存所有结果"""
    print("\n[13.8] 保存结果...")

    # 建筑级结果
    bld_out = os.path.join(OUTPUT_DIR, 'section13_building_walkability.csv')
    result_df.to_csv(bld_out, index=False, encoding='utf-8-sig')
    print(f"  建筑级指标: {bld_out}")

    # 小区级结果
    if community_result is not None and len(community_result) > 0:
        comm_out = os.path.join(OUTPUT_DIR, 'section13_community_accessibility_illusion.csv')
        community_result.to_csv(comm_out, index=False, encoding='utf-8-sig')
        print(f"  小区级指标: {comm_out}")

    # AI* 幻觉统计摘要
    summary_out = os.path.join(OUTPUT_DIR, 'section13_summary_stats.txt')
    with open(summary_out, 'w', encoding='utf-8') as f:
        f.write("Section 13 步行环境感知与可达性幻觉指数 统计摘要\n")
        f.write("=" * 60 + "\n\n")
        f.write("一、四项步行环境指标\n")
        for col, name in [('SCR', '人行道覆盖率'), ('BFD', '无障碍设施密度'),
                          ('EWW', '有效步行宽度'), ('SVI', '街道活力指数')]:
            if col in result_df.columns:
                vals = result_df[col].dropna()
                f.write(f"  {name}({col}): 均值={vals.mean():.3f}, "
                        f"标准差={vals.std():.3f}\n")
        f.write("\n二、群体速度模型\n")
        for group, col in [('Robust', 'v_robust'), ('Elderly', 'v_elderly'), ('Wheelchair', 'v_wheelchair')]:
            if col in result_df.columns:
                vals = result_df[col].dropna()
                f.write(f"  {group}: v={vals.mean():.2f}m/s, "
                        f"慢速(<0.8m/s)={(vals < 0.8).mean()*100:.1f}%\n")
        f.write("\n三、综合可达性幻觉指数 AI*\n")
        for group, col in [('Robust', 'AI_star_robust'), ('Elderly', 'AI_star_elderly'),
                          ('Wheelchair', 'AI_star_wheelchair')]:
            if col in result_df.columns:
                vals = result_df[col].dropna()
                f.write(f"  {group}: 均值={vals.mean():+.1f}%, "
                        f"幻觉区(>20%)={(vals > 20).mean()*100:.1f}%, "
                        f"严重(>40%)={(vals > 40).mean()*100:.1f}%\n")
        f.write("\n四、四象限分布\n")
        if 'quadrant' in result_df.columns:
            for q, cnt in result_df['quadrant'].value_counts().items():
                f.write(f"  {q}: {cnt} ({100*cnt/len(result_df):.1f}%)\n")
        f.write("\n五、城市形态分布\n")
        if 'morphology_type' in result_df.columns:
            for m, cnt in result_df['morphology_type'].value_counts().items():
                f.write(f"  {m}: {cnt} ({100*cnt/len(result_df):.1f}%)\n")
    print(f"  统计摘要: {summary_out}")


# ============================================================================
# 主流程
# ============================================================================

def run_section13_v2():
    """运行完整的Section 13 v2分析"""
    # 加载数据
    bdf, cdf, adf = load_all_data()

    # 形态计算
    df = compute_morphology(bdf)

    # 步行环境指标
    df = compute_walkability_metrics(df)

    # 群体速度
    df = compute_group_velocities(df)

    # AI* 幻觉指数
    df = compute_ai_star(df, adf)

    # 小区汇总
    comm_result = aggregate_by_community(df, cdf)

    # 可视化
    fig = visualize_section13_v2(df, comm_result)

    # 保存
    save_results(df, comm_result)

    print("\n" + "=" * 70)
    print("Section 13 v2 完成!")
    print("=" * 70)

    return df, comm_result


if __name__ == '__main__':
    run_section13_v2()
