# -*- coding: utf-8 -*-
"""
P3: Spatio-temporal Accessibility Illusion Modeling
时空可达性幻觉建模 - 核心创新指标

研究问题: 为什么某些居民区明明周边设施密度高，但实际可及性很差？
答案: 设施存在 ≠ 夜间可及 (时间维度剥夺)

指标体系:
1. SAI (Spatial Accessibility Index): 标准化白天可达性 (0-1)
2. TPI (Time Poverty Index): 夜间相对剥夺率 (%) — 从P2已有
3. SAII (Spatio-temporal Accessibility Illusion Index): SAI × TPI 复合剥夺
4. Vulnerability Score: 空间剥夺 × 时间剥夺 二维综合评分
5. Deprivation Typology: 剥夺类型分类
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy.stats import percentileofscore, spearmanr
from scipy.spatial import cKDTree

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT  = BASE  # output same directory
SEARCH_RADIUS_M = 1250

# ============================================================
# Load data
# ============================================================
print("Loading data...")
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
poi_df['supply'] = poi_df['facility_type'].apply(lambda t: SUPPLY_MAP.get(str(t), 1.0)).clip(0.3, 2.0)
poi_df['night_service'] = poi_df['night_service_final'].astype(bool)

comm_df = pd.read_csv(os.path.join(BASE, 'osm_data', 'nanshan_villages_with_building.csv'))
print("POI: {:,} (night={:,}, {:.1f}%)".format(
    len(poi_df), poi_df['night_service'].sum(), 100*poi_df['night_service'].mean()))
print("Communities: {:,}".format(len(comm_df)))

# ============================================================
# Build OD matrix (Haversine)
# ============================================================
print("\nBuilding OD matrix...")
comm_coords = comm_df[['lng', 'lat']].values
poi_coords = poi_df[['lng', 'lat']].values
N, M = len(comm_df), len(poi_df)

od_matrix = np.full((N, M), np.inf, dtype=np.float64)
R = 6371000
for i in range(N):
    clat = np.radians(comm_coords[i, 1])
    clon = np.deg2rad(comm_coords[i, 0])
    plat = np.radians(poi_coords[:, 1])
    dphi = np.radians(poi_coords[:, 1] - comm_coords[i, 1])
    dlam = np.radians(poi_coords[:, 0] - comm_coords[i, 0])
    a = np.sin(dphi/2)**2 + np.cos(clat)*np.cos(plat)*np.sin(dlam/2)**2
    od_matrix[i, :] = 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

print("OD range: [{:.0f}m, {:.0f}m]".format(od_matrix.min(), od_matrix.max()))

# ============================================================
# 2SFCA (vectorized)
# ============================================================
class TwoStepFloatingCatchmentArea:
    def step1(self, communities_df, facilities_df, od_matrix):
        supply = facilities_df[self.supply_col].values.astype(np.float64)
        reach_mask = (od_matrix <= self.search_radius)
        demand = communities_df[self.demand_col].values.astype(np.float64)
        total_demand = (reach_mask * demand[:, None]).sum(axis=0)
        R_j = np.where(total_demand > 0, supply / total_demand, 0.0)
        return R_j

    def step2(self, R_j, od_matrix):
        reach_mask = (od_matrix <= self.search_radius)
        A_i = (reach_mask * R_j[None, :]).sum(axis=1)
        return A_i

    def __init__(self, search_radius_m=1250, supply_col='supply', demand_col='population'):
        self.search_radius = search_radius_m
        self.supply_col = supply_col
        self.demand_col = demand_col

    def fit_transform(self, communities_df, facilities_df, od_matrix):
        R_j = self.step1(communities_df, facilities_df, od_matrix)
        A_i = self.step2(R_j, od_matrix)
        communities_df = communities_df.copy()
        communities_df['A_i_2sfca'] = A_i
        A_max = max(A_i.max(), 1e-9)
        communities_df['A_i_2sfca_norm'] = A_i / A_max
        return communities_df

# ============================================================
# Compute day/night accessibility
# ============================================================
print("\nComputing multi-period 2SFCA...")
results = comm_df[['id', 'lng', 'lat', 'community_type', 'population', 'money']].copy()
results = results.rename(columns={'id': 'community_id'})
if 'population' not in results.columns or results['population'].isna().all():
    results['population'] = np.random.randint(500, 5000, size=len(results))
comm_w = results[['community_id', 'population']].copy()
fac_all = poi_df[['supply']].copy()

model = TwoStepFloatingCatchmentArea(search_radius_m=SEARCH_RADIUS_M)
r_day = model.fit_transform(comm_w, fac_all, od_matrix)
results = results.merge(r_day[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']], on='community_id', how='left')
results = results.rename(columns={'A_i_2sfca_norm': 'SAI', 'A_i_2sfca': 'A_day'})

# Night
night_poi = poi_df[poi_df['night_service'] == True].copy().reset_index(drop=True)
night_idx = poi_df[poi_df['night_service'] == True].index.tolist()
od_night = od_matrix[:, night_idx]
fac_night = night_poi[['supply']].copy()
r_night = model.fit_transform(comm_w, fac_night, od_night)
results = results.merge(r_night[['community_id', 'A_i_2sfca', 'A_i_2sfca_norm']], on='community_id', how='left')
results = results.rename(columns={'A_i_2sfca_norm': 'SAI_night', 'A_i_2sfca': 'A_night'})

# TPI
day_v   = results['SAI'].fillna(0.0)
night_v = results['SAI_night'].fillna(0.0)
results['TPI'] = np.where(day_v > 0, (night_v - day_v) / day_v * 100, 0.0)
results['accessibility_gap'] = day_v - night_v

print("Day SAI:  mean={:.4f}, median={:.4f}".format(day_v.mean(), day_v.median()))
print("Night SAI: mean={:.4f}, median={:.4f}".format(night_v.mean(), night_v.median()))

# ============================================================
# P3: Spatio-temporal Accessibility Illusion Index (SAII)
# ============================================================
print("\n" + "="*55)
print("P3: Spatio-temporal Accessibility Illusion Modeling")
print("="*55)

# ---- 3a. SAI percentile rank (spatial deprivation) ----
results['SAI_pct'] = results['SAI'].rank(pct=True) * 100  # 越高=越可达

# ---- 3b. TPI (temporal deprivation) ----
# TPI = (night - day) / day * 100
# 正TPI = 夜间剥夺 (白天设施多,夜间少) → 幻觉效应
# 负TPI = 夜间优势 (夜间有独特资源)
# 转换: 无剥夺=0, 剥夺程度=正TPI, 夜间优势=-负TPI(转为正向)
# 标准化TPI剥夺度 (0-1): 基于剥夺方向
results['TPI_deprivation'] = np.where(
    results['TPI'] >= 0,          # 正TPI: 夜间剥夺
    results['TPI'],                # 直接用正值
    0.0                            # 负TPI: 无剥夺 (夜间优势社区)
)
# 归一化剥夺度 (0-1)
tpi_max = max(results['TPI_deprivation'].quantile(0.95), 0.01)
results['TPI_norm'] = (results['TPI_deprivation'] / tpi_max).clip(0, 1)

# ---- 3c. SAII (复合剥夺指数) ----
# SAII = (1 - SAI) * TPI_norm
# (1 - SAI) = 空间剥夺度
# TPI_norm = 时间剥夺度
# SAII > 0 且大 → 白天周边设施多但夜间服务少 = 时空幻觉
results['spatial_deprivation'] = 1.0 - results['SAI']
results['SAII'] = results['spatial_deprivation'] * results['TPI_norm']

# ---- 3d. Vulnerability Score (综合脆弱性) ----
# 标准化TPI到0-1区间 (用于合成)
tpi_d_max = results['TPI_deprivation'].quantile(0.95)
tpi_d_norm = (results['TPI_deprivation'] / tpi_d_max).clip(0, 1)
results['vulnerability'] = (results['spatial_deprivation'] + tpi_d_norm) / 2
# 加权脆弱性 (空间权重60%, 时间权重40%)
results['vulnerability_weighted'] = (
    0.6 * results['spatial_deprivation'] + 0.4 * tpi_d_norm
)

# ---- 3e. Deprivation Typology (剥夺类型学 - 修正版) ----
# 四象限分类
median_sai = results['SAI'].median()

def classify_deprivation(row):
    sp = row['spatial_deprivation']   # 1-SAI
    tp = row['TPI_norm']
    sai = row['SAI']

    # 双重剥夺: 高剥夺 + 高时间剥夺
    if sp >= 0.5 and tp >= 0.15:
        return '4-Dual Deprived'
    # 时间幻觉: 周边设施尚可(SAI>=中位数), 但夜间时间剥夺明显(tp>=0.05)
    elif sai >= median_sai and tp >= 0.05:
        return '2-Temporal Illusion'
    # 空间孤立: 空间服务不足, 但夜间相对均衡(无额外时间剥夺)
    elif sp >= 0.5 and tp < 0.05:
        return '3-Spatially Isolated'
    # 充足服务: 低空间剥夺 且 低时间剥夺
    else:
        return '1-Well-Served'

results['deprivation_type'] = results.apply(classify_deprivation, axis=1)

# ---- 3f. Accessibility Illusion Flag ----
# 幻觉定义: SAI > 中位数 但 TPI_deprivation > 0
# → 明明周边设施充足, 夜间却服务不足
median_sai = results['SAI'].median()
results['illusion_flag'] = (
    (results['SAI'] > median_sai) &
    (results['TPI_deprivation'] > 0)
).astype(int)
results['illusion_type'] = results.apply(
    lambda r: 'Accessibility Illusion' if r['illusion_flag'] == 1 else
              ('Night Advantage' if r['TPI'] < -5 else
               ('Dual Deprivation' if r['deprivation_type'] == '4-Dual Deprived' else 'Normal')),
    axis=1
)

# ============================================================
# Key Findings
# ============================================================
print("\n" + "="*55)
print("KEY FINDINGS: P3 - Spatio-temporal Accessibility Illusion")
print("="*55)

# SAII distribution
print("\n[SAII] Spatio-temporal Illusion Index:")
print("  mean={:.4f}, median={:.4f}, max={:.4f}".format(
    results['SAII'].mean(), results['SAII'].median(), results['SAII'].max()))
print("  75th pct={:.4f}, 90th pct={:.4f}".format(
    results['SAII'].quantile(0.75), results['SAII'].quantile(0.90)))

# Deprivation type
print("\n[Deprivation Typology]:")
for t, cnt in results['deprivation_type'].value_counts().sort_index().items():
    pct = 100 * cnt / len(results)
    print("  {}: {} ({:.1f}%)".format(t, cnt, pct))

# Accessibility illusion communities
n_illusion = results['illusion_flag'].sum()
n_total = len(results)
print("\n[Accessibility Illusion]:")
print("  Communities with illusion: {} / {} ({:.1f}%)".format(
    n_illusion, n_total, 100*n_illusion/n_total))

# Top illusion communities
print("\nTop 10 SAII (strongest illusion):")
cols = ['community_id', 'SAI', 'SAI_night', 'TPI', 'SAII', 'deprivation_type']
print(results.nlargest(10, 'SAII')[cols].to_string(index=False))

# Bottom SAII (well-served)
print("\nBottom 5 SAII (best served):")
print(results.nsmallest(5, 'SAII')[cols].to_string(index=False))

# By community_type
print("\n[SAII by community_type]:")
for ct, grp in results.groupby('community_type'):
    print("  {}: SAI={:.3f}, SAII={:.4f}, illusion={:.0f}%".format(
        ct, grp['SAI'].mean(), grp['SAII'].mean(), 100*grp['illusion_flag'].mean()))

# Correlations
print("\n[Correlation Analysis]:")
rho_sai_tpi = spearmanr(results['SAI'], results['TPI'])[0]
rho_sai_saii = spearmanr(results['SAI'], results['SAII'])[0]
rho_tpi_saii = spearmanr(results['TPI'], results['SAII'])[0]
print("  Spearman(SAI, TPI) = {:.3f}".format(rho_sai_tpi))
print("  Spearman(SAI, SAII) = {:.3f}".format(rho_sai_saii))
print("  Spearman(TPI, SAII) = {:.3f}".format(rho_tpi_saii))

# ============================================================
# Visualization
# ============================================================
print("\nGenerating visualizations...")
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('Nanshan District: Spatio-temporal Accessibility Illusion Analysis\n南山區時空可達性幻覺分析', fontsize=14, fontweight='bold')

# 1. SAI vs TPI scatter
ax1 = axes[0, 0]
colors = results['deprivation_type'].map({
    '4-Dual Deprived': '#d62728',
    '3-Spatially Isolated': '#ff7f0e',
    '2-Temporal Illusion': '#2ca02c',
    '1-Well-Served': '#1f77b4'
})
ax1.scatter(results['SAI'], results['TPI'], c=colors, alpha=0.6, s=30, edgecolors='white', linewidth=0.5)
ax1.axhline(0, color='gray', linestyle='--', linewidth=1)
ax1.axvline(results['SAI'].median(), color='gray', linestyle=':', linewidth=1, label='Median SAI')
ax1.set_xlabel('SAI (Spatial Accessibility Index)', fontsize=10)
ax1.set_ylabel('TPI (Time Poverty Index, %)', fontsize=10)
ax1.set_title('SAI vs TPI: Deprivation Quadrants\n時空剝奪象限圖', fontsize=11)
ax1.legend(handles=[
    mpatches.Patch(color='#d62728', label='4-Dual Deprived'),
    mpatches.Patch(color='#ff7f0e', label='3-Spatially Isolated'),
    mpatches.Patch(color='#2ca02c', label='2-Temporal Illusion'),
    mpatches.Patch(color='#1f77b4', label='1-Well-Served'),
], fontsize=8, loc='upper left')
ax1.grid(True, alpha=0.3)

# Quadrant labels
ax1.text(0.05, 0.9, 'SAII Zone\n時空幻覺區', transform=ax1.transAxes,
         fontsize=9, color='darkred', fontweight='bold',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

# 2. SAII histogram
ax2 = axes[0, 1]
ax2.hist(results['SAII'], bins=40, color='steelblue', edgecolor='white', alpha=0.8)
ax2.axvline(results['SAII'].quantile(0.90), color='red', linestyle='--', linewidth=2,
            label='90th pct ({:.3f})'.format(results['SAII'].quantile(0.90)))
ax2.axvline(results['SAII'].mean(), color='orange', linestyle='--', linewidth=2,
            label='Mean ({:.3f})'.format(results['SAII'].mean()))
ax2.set_xlabel('SAII (Spatio-temporal Illusion Index)', fontsize=10)
ax2.set_ylabel('Number of Communities', fontsize=10)
ax2.set_title('SAII Distribution\n時空幻覺指數分佈', fontsize=11)
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

# 3. Deprivation type bar
ax3 = axes[0, 2]
type_order = ['1-Well-Served', '2-Temporal Illusion', '3-Spatially Isolated', '4-Dual Deprived']
type_labels = ['充足服務\nWell-Served', '時間幻覺\nTemporal Illusion',
               '空間孤立\nSpatially Isolated', '雙重剝奪\nDual Deprived']
type_colors = ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728']
counts = [results['deprivation_type'].value_counts().get(t, 0) for t in type_order]
bars = ax3.barh(type_labels, counts, color=type_colors, edgecolor='white')
for bar, cnt in zip(bars, counts):
    ax3.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
             '{:.1f}%'.format(100*cnt/len(results)), va='center', fontsize=9)
ax3.set_xlabel('Number of Communities', fontsize=10)
ax3.set_title('Deprivation Type Distribution\n剝奪類型分佈', fontsize=11)
ax3.set_xlim(0, max(counts) * 1.2)
ax3.grid(True, alpha=0.3, axis='x')

# 4. SAI spatial map (lon vs lat colored by SAI)
ax4 = axes[1, 0]
sc = ax4.scatter(results['lng'], results['lat'], c=results['SAI'],
                  cmap='RdYlGn', alpha=0.7, s=25, edgecolors='white', linewidth=0.3)
ax4.set_xlabel('Longitude', fontsize=10)
ax4.set_ylabel('Latitude', fontsize=10)
ax4.set_title('Spatial Accessibility Index (Day)\n白天空間可達性', fontsize=11)
plt.colorbar(sc, ax=ax4, label='SAI', shrink=0.8)
ax4.grid(True, alpha=0.2)

# 5. TPI spatial map
ax5 = axes[1, 1]
sc2 = ax5.scatter(results['lng'], results['lat'], c=results['TPI_deprivation'],
                   cmap='YlOrRd', alpha=0.7, s=25, edgecolors='white', linewidth=0.3)
ax5.set_xlabel('Longitude', fontsize=10)
ax5.set_ylabel('Latitude', fontsize=10)
ax5.set_title('Time Poverty (Night Deprivation)\n夜間剝奪時間貧困指數', fontsize=11)
plt.colorbar(sc2, ax=ax5, label='TPI Deprivation (%)', shrink=0.8)
ax5.grid(True, alpha=0.2)

# 6. SAII spatial map (illusion index)
ax6 = axes[1, 2]
sc3 = ax6.scatter(results['lng'], results['lat'], c=results['SAII'],
                   cmap='plasma', alpha=0.7, s=25, edgecolors='white', linewidth=0.3,
                   vmin=0)
ax6.set_xlabel('Longitude', fontsize=10)
ax6.set_ylabel('Latitude', fontsize=10)
ax6.set_title('Accessibility Illusion Index (SAII)\n時空可達性幻覺指數', fontsize=11)
plt.colorbar(sc3, ax=ax6, label='SAII', shrink=0.8)
ax6.grid(True, alpha=0.2)

plt.tight_layout()
FIG_PATH = os.path.join(OUT, 'p3_accessibility_illusion_analysis.png')
plt.savefig(FIG_PATH, dpi=150, bbox_inches='tight', facecolor='white')
print("Figure saved: {}".format(FIG_PATH))
plt.close()

# ============================================================
# Save results CSV
# ============================================================
CSV_PATH = os.path.join(OUT, 'p3_accessibility_results.csv')
export_cols = [
    'community_id', 'lng', 'lat', 'community_type',
    'SAI', 'SAI_night', 'spatial_deprivation',
    'TPI', 'TPI_deprivation', 'TPI_norm',
    'SAII', 'vulnerability', 'vulnerability_weighted',
    'deprivation_type', 'illusion_flag', 'illusion_type'
]
results[export_cols].to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
print("Results saved: {}".format(CSV_PATH))

# ============================================================
# Summary statistics table
# ============================================================
print("\n" + "="*55)
print("P3 SUMMARY TABLE")
print("="*55)
summary_data = {
    'Metric': ['SAI (Day)', 'SAI (Night)', 'TPI (%)', 'TPI Deprivation (%)',
                'SAII', 'Vulnerability', 'Illusion Flag Rate'],
    'Mean':   [f"{results['SAI'].mean():.4f}", f"{results['SAI_night'].mean():.4f}",
               f"{results['TPI'].mean():.1f}", f"{results['TPI_deprivation'].mean():.1f}",
               f"{results['SAII'].mean():.4f}", f"{results['vulnerability'].mean():.4f}",
               f"{results['illusion_flag'].mean()*100:.1f}%"],
    'Median': [f"{results['SAI'].median():.4f}", f"{results['SAI_night'].median():.4f}",
               f"{results['TPI'].median():.1f}", f"{results['TPI_deprivation'].median():.1f}",
               f"{results['SAII'].median():.4f}", f"{results['vulnerability'].median():.4f}",
               '-'],
    'Std':    [f"{results['SAI'].std():.4f}", f"{results['SAI_night'].std():.4f}",
               f"{results['TPI'].std():.1f}", f"{results['TPI_deprivation'].std():.1f}",
               f"{results['SAII'].std():.4f}", f"{results['vulnerability'].std():.4f}", '-'],
    'Min':    [f"{results['SAI'].min():.4f}", f"{results['SAI_night'].min():.4f}",
               f"{results['TPI'].min():.1f}", f"{results['TPI_deprivation'].min():.1f}",
               f"{results['SAII'].min():.4f}", f"{results['vulnerability'].min():.4f}", '-'],
    'Max':    [f"{results['SAI'].max():.4f}", f"{results['SAI_night'].max():.4f}",
               f"{results['TPI'].max():.1f}", f"{results['TPI_deprivation'].max():.1f}",
               f"{results['SAII'].max():.4f}", f"{results['vulnerability'].max():.4f}", '-'],
}
summary_df = pd.DataFrame(summary_data)
print(summary_df.to_string(index=False))

print("\n*** P3 COMPLETE ***")
print("Output: p3_accessibility_illusion_analysis.png")
print("Data:   p3_accessibility_results.csv")
