# -*- coding: utf-8 -*-
"""
Notebook Cell: P3b - 时空可达性幻觉建模 (修正版)
修正内容:
1. TPI_norm 改用对称归一化 |TPI|/max(|TPI|) — 保留夜间优势信息
2. 四象限分类正确划分 (Temporal Illusion / Night Advantage / Dual Deprived / Well-Served)
3. 改进图表 (象限线、标注、幻想区高亮)

依赖: Cell 25 的 acc_results, poi_df, 坐标系
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

plt.rcParams['font.family'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC',
    'SimSun', 'AR PL UMing CN', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
# 复用 acc_results (Cell 25 产出)
# ============================================================
results = acc_results.copy()

# 标准化列名
results = results.rename(columns={
    'A_i_2sfca_norm_day':   'SAI',
    'A_i_2sfca_norm_night': 'SAI_night',
})
if 'lng' not in results.columns and 'center_lng' in results.columns:
    results = results.rename(columns={'center_lng': 'lng', 'center_lat': 'lat'})
if 'community_id' not in results.columns and 'id' in results.columns:
    results = results.rename(columns={'id': 'community_id'})

# ============================================================
# P3b 核心指标 (修正版)
# ============================================================
print("=" * 60)
print("P3b: Spatio-temporal Accessibility Illusion Modeling (修正版)")
print("=" * 60)

# 1. SAI percentile rank
results['SAI_pct'] = results['SAI'].rank(pct=True) * 100

# 2. TPI 对称归一化
# |TPI|越大 = 偏离均衡状态越远
tpi_abs = results['TPI'].abs()
tpi_abs_max = tpi_abs.quantile(0.95)
results['TPI_sym'] = (tpi_abs / tpi_abs_max).clip(0, 1)

# TPI_dep (仅剥夺方向): 正TPI → 剥夺度, 负TPI → 0
results['TPI_dep'] = results['TPI'].clip(lower=0)
tpi_dep_max = max(results['TPI_dep'].quantile(0.95), 0.01)
results['TPI_dep_norm'] = (results['TPI_dep'] / tpi_dep_max).clip(0, 1)

# 3. Spatial deprivation
results['spatial_dep'] = 1.0 - results['SAI']

# 4. SAII (复合剥夺指数)
results['SAII'] = results['spatial_dep'] * results['TPI_dep_norm']

# 5. 四象限分类 (基于 SAI_pct 和 TPI 符号)
median_pct = 50.0
median_sai = results['SAI'].median()

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

results['deprivation_type'] = results['quadrant'].map({
    'Q1-Temporal Illusion': '2-Temporal Illusion',
    'Q2-Night Advantage':    '1-Night Advantage',
    'Q3-Dual Deprived':    '4-Dual Deprived',
    'Q4-Spatial Isolated':  '3-Spatial Isolated',
})

# 6. Illusion flag
results['illusion_flag'] = (
    (results['SAI'] >= median_sai) &
    (results['TPI'] >= 0)
).astype(int)

# 7. Vulnerability
results['vulnerability'] = (results['spatial_dep'] + results['TPI_dep_norm']) / 2
results['vuln_weighted'] = 0.6 * results['spatial_dep'] + 0.4 * results['TPI_dep_norm']

# ============================================================
# 输出结果
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

n_illus = int(results['illusion_flag'].sum())
print("\n[Accessibility Illusion]: {} / {} ({:.1f}%)".format(
    n_illus, len(results), 100*n_illus/len(results)))

print("\nTop 10 by SAII:")
print(results.nlargest(10, 'SAII')[
    ['community_id', 'SAI', 'SAI_night', 'TPI', 'SAII', 'deprivation_type']
].to_string(index=False))

print("\nBy community_type:")
for ct, grp in results.groupby('community_type'):
    print("  {}: SAI={:.3f}, SAII={:.4f}, illusion={:.0f}%".format(
        ct, grp['SAI'].mean(), grp['SAII'].mean(), 100*grp['illusion_flag'].mean()))

print("\n[Correlations]:")
for a, b in [('SAI', 'TPI'), ('SAI', 'SAII'), ('TPI', 'SAII')]:
    rho = spearmanr(results[a], results[b])[0]
    print("  Spearman({:6s}, {:6s}) = {:.3f}".format(a, b, rho))

# ============================================================
# 可视化 (6 图)
# ============================================================
print("\nGenerating figures...")
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle(
    'Nanshan District: Spatio-temporal Accessibility Illusion Analysis (P3b)\n'
    '南山區時空可達性幻覺分析',
    fontsize=13, fontweight='bold', y=1.02
)

QUAD_COLORS = {
    'Q1-Temporal Illusion': '#e74c3c',
    'Q2-Night Advantage':    '#27ae60',
    'Q3-Dual Deprived':     '#8e44ad',
    'Q4-Spatial Isolated':   '#f39c12',
}
LABEL_CN = {
    'Q1-Temporal Illusion': '時空幻覺區',
    'Q2-Night Advantage':    '夜間優勢區',
    'Q3-Dual Deprived':      '雙重剝奪區',
    'Q4-Spatial Isolated':   '空間孤立區',
}

# Panel 1: SAI vs TPI 四象限图
ax1 = axes[0, 0]
for q, grp in results.groupby('quadrant'):
    ax1.scatter(grp['SAI'], grp['TPI'],
                c=QUAD_COLORS[q], alpha=0.65, s=40,
                edgecolors='white', linewidth=0.5, label=LABEL_CN[q])
ax1.axhline(0, color='black', linewidth=1.5)
ax1.axvline(median_sai, color='black', linewidth=1.5, linestyle=':')
ax1.set_xlabel('SAI (Day)', fontsize=10)
ax1.set_ylabel('TPI (%)', fontsize=10)
ax1.set_title('SAI vs TPI: Four Quadrants\n時空剝奪四象限圖', fontsize=11)
ax1.legend(fontsize=8, loc='upper left')
ax1.grid(True, alpha=0.25)
# 象限标注
ax1.text(0.97, 0.97, 'Q1\n時空幻覺', transform=ax1.transAxes, fontsize=9,
         color='darkred', fontweight='bold', ha='right', va='top',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fdecea', alpha=0.8))
ax1.text(0.03, 0.97, 'Q2\n夜間優勢', transform=ax1.transAxes, fontsize=9,
         color='darkgreen', fontweight='bold', ha='left', va='top',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#eafaf1', alpha=0.8))
ax1.text(0.03, 0.03, 'Q4\n空間孤立', transform=ax1.transAxes, fontsize=9,
         color='darkorange', fontweight='bold', ha='left', va='bottom',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#fff8e1', alpha=0.8))
ax1.text(0.97, 0.03, 'Q3\n雙重剝奪', transform=ax1.transAxes, fontsize=9,
         color='purple', fontweight='bold', ha='right', va='bottom',
         bbox=dict(boxstyle='round,pad=0.3', facecolor='#f4ecf7', alpha=0.8))

# Panel 2: SAII 直方图
ax2 = axes[0, 1]
saii_vals = results['SAII'].values
ax2.hist(saii_vals, bins=40, color='#3498db', edgecolor='white', alpha=0.85)
for thresh, lbl, clr in [(0.75, '75th pct', 'orange'), (0.90, '90th pct', 'red')]:
    v = np.percentile(saii_vals, thresh * 100)
    ax2.axvline(v, color=clr, linestyle='--', linewidth=2,
                 label='{}={:.3f}'.format(lbl, v))
ax2.axvline(saii_vals.mean(), color='steelblue', linestyle='-', linewidth=2,
            label='Mean={:.3f}'.format(saii_vals.mean()))
ax2.set_xlabel('SAII', fontsize=10)
ax2.set_ylabel('Count', fontsize=10)
ax2.set_title('SAII Distribution\n時空幻覺指數分佈', fontsize=11)
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.3)

# Panel 3: 剥夺类型条形图
ax3 = axes[0, 2]
type_order = [
    ('1-Night Advantage',   '夜間優勢\nNight Adv.',         '#27ae60'),
    ('2-Temporal Illusion', '時空幻覺\nTemporal Illusion',  '#e74c3c'),
    ('3-Spatial Isolated', '空間孤立\nSpatial Isolated',    '#f39c12'),
    ('4-Dual Deprived',    '雙重剝奪\nDual Deprived',      '#8e44ad'),
]
labels = [m[1] for m in type_order]
counts = [results['deprivation_type'].value_counts().get(m[0], 0) for m in type_order]
colors = [m[2] for m in type_order]
pcts   = [100 * c / len(results) for c in counts]
bars = ax3.barh(labels, counts, color=colors, edgecolor='white', height=0.6)
for bar, cnt, pct in zip(bars, counts, pcts):
    ax3.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
             '{} ({:.1f}%)'.format(cnt, pct), va='center', fontsize=10)
ax3.set_xlabel('Number of Communities', fontsize=10)
ax3.set_title('Deprivation Typology\n剝奪類型分佈', fontsize=11)
ax3.set_xlim(0, max(counts) * 1.3)
ax3.grid(True, alpha=0.3, axis='x')

# Panel 4: SAI 空间地图
ax4 = axes[1, 0]
sc4 = ax4.scatter(results['lng'], results['lat'], c=results['SAI'],
                   cmap='RdYlGn', alpha=0.75, s=25,
                   edgecolors='white', linewidth=0.3, vmin=0, vmax=1)
ax4.set_xlabel('Longitude', fontsize=10)
ax4.set_ylabel('Latitude', fontsize=10)
ax4.set_title('Day SAI Map (Spatial Accessibility)\n白天空間可達性', fontsize=11)
plt.colorbar(sc4, ax=ax4, label='SAI', shrink=0.85)
ax4.grid(True, alpha=0.2)

# Panel 5: TPI 空间地图
ax5 = axes[1, 1]
sc5 = ax5.scatter(results['lng'], results['lat'], c=results['TPI'],
                   cmap='RdBu_r', alpha=0.75, s=25,
                   edgecolors='white', linewidth=0.3,
                   vmin=-60, vmax=60)
ax5.set_xlabel('Longitude', fontsize=10)
ax5.set_ylabel('Latitude', fontsize=10)
ax5.set_title('TPI Map (Red=Deprived, Blue=Advantage)\n夜間剝奪指數', fontsize=11)
plt.colorbar(sc5, ax=ax5, label='TPI (%)', shrink=0.85)
ax5.grid(True, alpha=0.2)

# Panel 6: SAII 四象限空间地图
ax6 = axes[1, 2]
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
plt.savefig('p3b_accessibility_illusion_analysis.png', dpi=150,
            bbox_inches='tight', facecolor='white')
print("Figure saved: p3b_accessibility_illusion_analysis.png")
plt.show()

# 保存到 acc_results
acc_results = results.copy()

# 保存 CSV
export_cols = [
    'community_id', 'lng', 'lat', 'community_type',
    'SAI', 'SAI_night', 'SAI_pct', 'spatial_dep',
    'TPI', 'TPI_dep', 'TPI_dep_norm', 'TPI_sym',
    'SAII', 'vulnerability', 'vuln_weighted',
    'quadrant', 'deprivation_type', 'illusion_flag'
]
present = [c for c in export_cols if c in results.columns]
results[present].to_csv('p3b_accessibility_results.csv',
                       index=False, encoding='utf-8-sig')
print("Results saved: p3b_accessibility_results.csv")

# 汇总表
print("\n" + "=" * 55)
print("P3b FINAL SUMMARY TABLE")
print("=" * 55)
summary = pd.DataFrame({
    'Metric':  ['SAI (Day)', 'SAI (Night)', 'TPI (%)', 'TPI_dep_norm',
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
})
print(summary.to_string(index=False))

print("\n*** P3b Cell Complete ***")
