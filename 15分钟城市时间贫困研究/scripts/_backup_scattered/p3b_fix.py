# -*- coding: utf-8 -*-
"""
P3b: 修正时空可达性幻觉建模
修正内容:
1. TPI_norm 改用对称归一化 |TPI|/max(|TPI|) — 保留夜间优势信息
2. 四象限分类正确划分 (Temporal Illusion / Night Advantage / Dual Deprived / Well-Served)
3. 改进图表 (象限线、标注、幻想区高亮)
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
from matplotlib.lines import Line2D
from scipy.stats import spearmanr

np.random.seed(42)

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT  = BASE
SEARCH_RADIUS_M = 1250

# ============================================================
# Load & preprocess
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
# OD matrix (Haversine)
# ============================================================
print("\nBuilding OD matrix...")
comm_c = comm_df[['lng', 'lat']].values
poi_c   = poi_df[['lng', 'lat']].values
N, M = len(comm_df), len(poi_df)

od = np.zeros((N, M), dtype=np.float64)
for i in range(N):
    clat = np.radians(comm_c[i, 1])
    clon = np.deg2rad(comm_c[i, 0])
    plat = np.radians(poi_c[:, 1])
    dphi = np.radians(poi_c[:, 1] - comm_c[i, 1])
    dlam = np.radians(poi_c[:, 0] - comm_c[i, 0])
    a = np.sin(dphi/2)**2 + np.cos(clat)*np.cos(plat)*np.sin(dlam/2)**2
    od[i, :] = 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

print("OD range: [{:.0f}m, {:.0f}m]".format(od.min(), od.max()))

# ============================================================
# 2SFCA
# ============================================================
class TwoStepFloatingCatchmentArea:
    def __init__(self, search_radius_m=1250, supply_col='supply'):
        self.search_radius = search_radius_m
        self.supply_col = supply_col

    def fit_transform(self, communities_df, facilities_df, od_matrix):
        communities_df = communities_df.copy()  # 避免副作用
        facilities_df = facilities_df.copy()
        supply = facilities_df[self.supply_col].values.astype(np.float64)
        demand = communities_df['population'].values.astype(np.float64)
        reach = (od_matrix <= self.search_radius).astype(np.float64)
        total_demand = (reach * demand[:, None]).sum(axis=0)
        R_j = np.where(total_demand > 0, supply / total_demand, 0.0)
        A_i = (reach * R_j[None, :]).sum(axis=1)
        communities_df['A_i_2sfca'] = A_i
        A_max = max(A_i.max(), 1e-9)
        communities_df['SAI'] = A_i / A_max
        return communities_df

# Build results
results = comm_df[['id', 'lng', 'lat', 'community_type', 'population', 'money']].copy()
results = results.rename(columns={'id': 'community_id'})
if results['population'].isna().all():
    results['population'] = np.random.randint(500, 5000, size=len(results))
results['population'] = results['population'].fillna(results['population'].median())

fac_all  = poi_df[['supply']].copy()
fac_night = poi_df[poi_df['night_service'] == True][['supply']].copy().reset_index(drop=True)
night_idx = poi_df[poi_df['night_service'] == True].index.tolist()
od_night = od[:, night_idx]

model = TwoStepFloatingCatchmentArea(search_radius_m=SEARCH_RADIUS_M)
comm_w = comm_df[['id', 'lng', 'lat', 'community_type', 'population', 'money']].copy()
comm_w = comm_w.rename(columns={'id': 'community_id'})
comm_w['population'] = comm_w['population'].fillna(comm_w['population'].median())

r_day   = model.fit_transform(comm_w, fac_all, od)
r_night = model.fit_transform(comm_w, fac_night, od_night)

results = comm_w.copy()
results['SAI']       = r_day['SAI']
results['SAI_night'] = r_night['SAI']

# TPI
day_v = results['SAI'].fillna(0.0)
nit_v = results['SAI_night'].fillna(0.0)
results['TPI'] = np.where(day_v > 0, (nit_v - day_v) / day_v * 100, 0.0)
results['gap'] = day_v - nit_v

print("\nDay SAI:  mean={:.4f}, median={:.4f}".format(day_v.mean(), day_v.median()))
print("Night SAI: mean={:.4f}, median={:.4f}".format(nit_v.mean(), nit_v.median()))
print("TPI: mean={:.1f}%, median={:.1f}%".format(results['TPI'].mean(), results['TPI'].median()))

# ============================================================
# P3b 核心指标 (修正版)
# ============================================================
print("\n" + "="*55)
print("P3b: Spatio-temporal Accessibility Illusion Modeling (修正版)")
print("="*55)

# ---- 1. SAI percentile rank ----
results['SAI_pct'] = results['SAI'].rank(pct=True) * 100

# ---- 2. TPI_sym (对称归一化) ----
# |TPI|越大 = 偏离均衡状态越远 (无论是剥夺还是优势)
tpi_abs = results['TPI'].abs()
tpi_abs_max = tpi_abs.quantile(0.95)
results['TPI_sym'] = (tpi_abs / tpi_abs_max).clip(0, 1)

# TPI_dep (仅剥夺方向): 正TPI -> 剥夺度, 负TPI -> 0
results['TPI_dep'] = results['TPI'].clip(lower=0)
# 归一化剥夺度
tpi_dep_max = max(results['TPI_dep'].quantile(0.95), 0.01)
results['TPI_dep_norm'] = (results['TPI_dep'] / tpi_dep_max).clip(0, 1)

# ---- 3. Spatial deprivation ----
results['spatial_dep'] = 1.0 - results['SAI']

# ---- 4. SAII (复合剥夺指数) ----
# 仅在正TPI时有效; 负TPI=夜间优势 → SAII=0
results['SAII'] = results['spatial_dep'] * results['TPI_dep_norm']

# ---- 5. 四象限剥夺分类 (基于SAI_pct和TPI符号) ----
median_pct = 50.0  # SAI百分位中位数

# np.select向量化避免pandas apply bug
conditions = [
    (results['SAI_pct'] >= median_pct) & (results['TPI'] >= 0),
    (results['SAI_pct'] >= median_pct) & (results['TPI'] < 0),
    (results['SAI_pct'] < median_pct)  & (results['TPI'] >= 0),
]
choices = [
    'Q1-Temporal Illusion',
    'Q2-Night Advantage',
    'Q3-Dual Deprived',
]
results['quadrant'] = np.select(conditions, choices, default='Q4-Spatial Isolated')

# 更友好的分类标签
results['deprivation_type'] = results['quadrant'].map({
    'Q1-Temporal Illusion':  '2-Temporal Illusion',
    'Q2-Night Advantage':     '1-Night Advantage',
    'Q3-Dual Deprived':      '4-Dual Deprived',
    'Q4-Spatial Isolated':    '3-Spatial Isolated',
})

# ---- 6. Illusion flag ----
# 幻觉: SAI >= 中位数 + TPI >= 0
median_sai = results['SAI'].median()
results['illusion_flag'] = (
    (results['SAI'] >= median_sai) &
    (results['TPI'] >= 0)
).astype(int)

# ---- 7. Vulnerability ----
results['vulnerability'] = (results['spatial_dep'] + results['TPI_dep_norm']) / 2
results['vuln_weighted'] = 0.6 * results['spatial_dep'] + 0.4 * results['TPI_dep_norm']

# ============================================================
# Key Findings
# ============================================================
print("\n[SAII] Spatio-temporal Illusion Index:")
print("  mean={:.4f}, median={:.4f}, max={:.4f}".format(
    results['SAII'].mean(), results['SAII'].median(), results['SAII'].max()))
print("  75th={:.4f}, 90th={:.4f}".format(
    results['SAII'].quantile(0.75), results['SAII'].quantile(0.90)))

print("\n[Four Quadrant Distribution]:")
for q, cnt in results['quadrant'].value_counts().sort_index().items():
    print("  {}: {} ({:.1f}%)".format(q, cnt, 100*cnt/len(results)))

print("\n[Deprivation Type]:")
for t, cnt in results['deprivation_type'].value_counts().sort_index().items():
    print("  {}: {} ({:.1f}%)".format(t, cnt, 100*cnt/len(results)))

n_illus = results['illusion_flag'].sum()
print("\n[Accessibility Illusion]: {} / {} ({:.1f}%)".format(
    n_illus, len(results), 100*n_illus/len(results)))

print("\nTop 10 by SAII:")
cols = ['community_id', 'SAI', 'SAI_night', 'TPI', 'SAII', 'deprivation_type']
print(results.nlargest(10, 'SAII')[cols].to_string(index=False))

print("\nBy community_type:")
for ct, grp in results.groupby('community_type'):
    print("  {}: SAI={:.3f}, SAII={:.4f}, illusion={:.0f}%".format(
        ct, grp['SAI'].mean(), grp['SAII'].mean(), 100*grp['illusion_flag'].mean()))

print("\n[Correlations]:")
for a, b in [('SAI','TPI'), ('SAI','SAII'), ('TPI','SAII')]:
    rho = spearmanr(results[a], results[b])[0]
    print("  Spearman({:6s}, {:6s}) = {:.3f}".format(a, b, rho))

# ============================================================
# Visualization (改进版)
# ============================================================
print("\nGenerating figures...")
plt.rcParams['font.family'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC',
    'SimSun', 'AR PL UMing CN', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle(
    'Nanshan District: Spatio-temporal Accessibility Illusion Analysis\n'
    '南山區時空可達性幻覺分析 (P3b)',
    fontsize=14, fontweight='bold', y=1.02
)

QUAD_COLORS = {
    'Q1-Temporal Illusion': '#e74c3c',   # 红
    'Q2-Night Advantage':   '#27ae60',   # 绿
    'Q3-Dual Deprived':    '#8e44ad',   # 紫
    'Q4-Spatial Isolated':  '#f39c12',   # 橙
}
LABEL_CN = {
    'Q1-Temporal Illusion': '時空幻覺區',
    'Q2-Night Advantage':   '夜間優勢區',
    'Q3-Dual Deprived':    '雙重剝奪區',
    'Q4-Spatial Isolated':  '空間孤立區',
}

# -------- Panel 1: SAI vs TPI (四象限图) --------
ax1 = axes[0, 0]
for q, grp in results.groupby('quadrant'):
    ax1.scatter(grp['SAI'], grp['TPI'],
                c=QUAD_COLORS[q], alpha=0.65, s=40,
                edgecolors='white', linewidth=0.5, label=q)

ax1.axhline(0, color='black', linewidth=1.5)
ax1.axvline(median_sai, color='black', linewidth=1.5, linestyle=':')
ax1.set_xlabel('SAI (Spatial Accessibility Index, day)', fontsize=10)
ax1.set_ylabel('TPI (Time Poverty Index, %)', fontsize=10)
ax1.set_title('SAI vs TPI: Four Quadrants\n時空剝奪四象限圖', fontsize=11)
ax1.legend(fontsize=8, loc='upper left')
ax1.grid(True, alpha=0.25)

# 象限标签
ax1.text(0.95, 0.95, 'Q1\n時空幻覺',
         transform=ax1.transAxes, fontsize=9, color='darkred', fontweight='bold',
         ha='right', va='top',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdecea', alpha=0.8))
ax1.text(0.02, 0.95, 'Q2\n夜間優勢',
         transform=ax1.transAxes, fontsize=9, color='darkgreen', fontweight='bold',
         ha='left', va='top',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#eafaf1', alpha=0.8))
ax1.text(0.02, 0.05, 'Q4\n空間孤立',
         transform=ax1.transAxes, fontsize=9, color='darkorange', fontweight='bold',
         ha='left', va='bottom',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff8e1', alpha=0.8))
ax1.text(0.95, 0.05, 'Q3\n雙重剝奪',
         transform=ax1.transAxes, fontsize=9, color='purple', fontweight='bold',
         ha='right', va='bottom',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#f4ecf7', alpha=0.8))

# -------- Panel 2: SAII histogram --------
ax2 = axes[0, 1]
saii_vals = results['SAII'].values
ax2.hist(saii_vals, bins=40, color='#3498db', edgecolor='white', alpha=0.85)
for thresh, lbl, clr in [(0.75,'75th pct','orange'), (0.90,'90th pct','red')]:
    v = np.percentile(saii_vals, thresh*100)
    ax2.axvline(v, color=clr, linestyle='--', linewidth=2, label='{}={:.3f}'.format(lbl, v))
ax2.axvline(saii_vals.mean(), color='steelblue', linestyle='-', linewidth=2, label='Mean={:.3f}'.format(saii_vals.mean()))
ax2.set_xlabel('SAII (Spatio-temporal Illusion Index)', fontsize=10)
ax2.set_ylabel('Count', fontsize=10)
ax2.set_title('SAII Distribution\n時空幻覺指數分佈', fontsize=11)
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

# -------- Panel 3: Deprivation type bar --------
ax3 = axes[0, 2]
type_map = [
    ('1-Night Advantage',    '夜間優勢\nNight Adv.',  '#27ae60'),
    ('2-Temporal Illusion',  '時空幻覺\nTemporal Illusion','#e74c3c'),
    ('3-Spatial Isolated',   '空間孤立\nSpatial Isolated',  '#f39c12'),
    ('4-Dual Deprived',      '雙重剝奪\nDual Deprived',    '#8e44ad'),
]
labels   = [m[1] for m in type_map]
counts  = [results['deprivation_type'].value_counts().get(m[0], 0) for m in type_map]
colors  = [m[2] for m in type_map]
pcts     = [100*c/len(results) for c in counts]

bars = ax3.barh(labels, counts, color=colors, edgecolor='white', height=0.6)
for bar, cnt, pct in zip(bars, counts, pcts):
    ax3.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
             '{} ({:.1f}%)'.format(cnt, pct), va='center', fontsize=10)
ax3.set_xlabel('Number of Communities', fontsize=10)
ax3.set_title('Deprivation Typology\n剝奪類型分佈', fontsize=11)
ax3.set_xlim(0, max(counts) * 1.3)
ax3.grid(True, alpha=0.3, axis='x')

# -------- Panel 4: SAI spatial map --------
ax4 = axes[1, 0]
sc4 = ax4.scatter(results['lng'], results['lat'], c=results['SAI'],
                    cmap='RdYlGn', alpha=0.75, s=25,
                    edgecolors='white', linewidth=0.3, vmin=0, vmax=1)
ax4.set_xlabel('Longitude', fontsize=10)
ax4.set_ylabel('Latitude', fontsize=10)
ax4.set_title('Day SAI Map (Spatial Accessibility)\n白天空間可達性', fontsize=11)
plt.colorbar(sc4, ax=ax4, label='SAI', shrink=0.85)
ax4.grid(True, alpha=0.2)

# -------- Panel 5: TPI spatial map --------
ax5 = axes[1, 1]
sc5 = ax5.scatter(results['lng'], results['lat'], c=results['TPI'],
                    cmap='RdBu_r', alpha=0.75, s=25,
                    edgecolors='white', linewidth=0.3,
                    vmin=-60, vmax=60)
ax5.set_xlabel('Longitude', fontsize=10)
ax5.set_ylabel('Latitude', fontsize=10)
ax5.set_title('TPI Map (Red=Deprived, Blue=Advantage)\n夜間剝奪指數 (紅=剝奪, 藍=優勢)', fontsize=11)
plt.colorbar(sc5, ax=ax5, label='TPI (%)', shrink=0.85)
ax5.grid(True, alpha=0.2)

# -------- Panel 6: SAII spatial map (illusion) --------
ax6 = axes[1, 2]
# Color by quadrant
for q, grp in results.groupby('quadrant'):
    ax6.scatter(grp['lng'], grp['lat'],
                c=QUAD_COLORS[q], alpha=0.7, s=25,
                edgecolors='white', linewidth=0.3,
                label=LABEL_CN[q])
ax6.set_xlabel('Longitude', fontsize=10)
ax6.set_ylabel('Latitude', fontsize=10)
ax6.set_title('Accessibility Illusion Map (by Quadrant)\n時空可達性幻覺地圖', fontsize=11)
ax6.legend(fontsize=8, loc='upper left', framealpha=0.85)
ax6.grid(True, alpha=0.2)

plt.tight_layout()
FIG_PATH = os.path.join(OUT, 'p3b_accessibility_illusion_analysis.png')
plt.savefig(FIG_PATH, dpi=150, bbox_inches='tight', facecolor='white')
print("Figure saved: {}".format(FIG_PATH))
plt.close()

# ============================================================
# Save results
# ============================================================
CSV_PATH = os.path.join(OUT, 'p3b_accessibility_results.csv')
export_cols = [
    'community_id', 'lng', 'lat', 'community_type',
    'SAI', 'SAI_night', 'SAI_pct', 'spatial_dep',
    'TPI', 'TPI_dep', 'TPI_dep_norm', 'TPI_sym',
    'SAII', 'vulnerability', 'vuln_weighted',
    'quadrant', 'deprivation_type', 'illusion_flag'
]
results[export_cols].to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
print("Results saved: {}".format(CSV_PATH))

# ============================================================
# Summary table
# ============================================================
print("\n" + "="*55)
print("P3b FINAL SUMMARY TABLE")
print("="*55)
summary = {
    'Metric': ['SAI (Day)', 'SAI (Night)', 'TPI (%)', 'TPI_dep_norm',
                'SAII', 'Vulnerability', 'Illusion Flag Rate'],
    'Mean':   [f"{results['SAI'].mean():.4f}", f"{results['SAI_night'].mean():.4f}",
               f"{results['TPI'].mean():.1f}", f"{results['TPI_dep_norm'].mean():.4f}",
               f"{results['SAII'].mean():.4f}", f"{results['vulnerability'].mean():.4f}",
               f"{results['illusion_flag'].mean()*100:.1f}%"],
    'Median': [f"{results['SAI'].median():.4f}", f"{results['SAI_night'].median():.4f}",
               f"{results['TPI'].median():.1f}", f"{results['TPI_dep_norm'].median():.4f}",
               f"{results['SAII'].median():.4f}", f"{results['vulnerability'].median():.4f}", '-'],
    'Min':    [f"{results['SAI'].min():.4f}", f"{results['SAI_night'].min():.4f}",
               f"{results['TPI'].min():.1f}", f"{results['TPI_dep_norm'].min():.4f}",
               f"{results['SAII'].min():.4f}", f"{results['vulnerability'].min():.4f}", '-'],
    'Max':    [f"{results['SAI'].max():.4f}", f"{results['SAI_night'].max():.4f}",
               f"{results['TPI'].max():.1f}", f"{results['TPI_dep_norm'].max():.4f}",
               f"{results['SAII'].max():.4f}", f"{results['vulnerability'].max():.4f}", '-'],
}
print(pd.DataFrame(summary).to_string(index=False))

print("\n*** P3b COMPLETE ***")
