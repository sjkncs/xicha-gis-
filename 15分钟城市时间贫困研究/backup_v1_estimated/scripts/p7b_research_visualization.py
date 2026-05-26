# -*- coding: utf-8 -*-
"""
P7b: 研究级可视化 - 基于真实路网可达性分析
生成发表级图表用于SCI论文
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# 字体设置
plt.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 11

# 南山区范围
NS = {'west': 113.85, 'east': 114.05, 'south': 22.45, 'north': 22.65}

# 颜色方案
TPI_CMAP = LinearSegmentedColormap.from_list('tpi',
    ['#1a9850', '#91cf60', '#d9ef8b', '#fee08b', '#fdae61', '#f46d43', '#d73027'])
TPI_NORM = mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=350)

print("=" * 70)
print("P7b: 研究级可视化 - 路网可达性分析")
print("=" * 70)

# 加载数据
results = pd.read_csv(f"{BASE}/p7_network_accessibility_results.csv")
road_ns = gpd.read_file(f"{BASE}/osm_data/nanshan_road_network.shp")
print(f"小区: {len(results)}, 路网: {len(road_ns)}")

# 创建GeoDataFrame
geometry = [Point(xy) for xy in zip(results['lng'], results['lat'])]
gdf = gpd.GeoDataFrame(results, geometry=geometry, crs='EPSG:4326')

# 投影
road_proj = road_ns.to_crs('EPSG:3857')
gdf_proj = gdf.to_crs('EPSG:3857')

# 南山区中心
center_lon = (NS['west'] + NS['east']) / 2
center_lat = (NS['south'] + NS['north']) / 2

def fmt_lon(x, pos=None):
    return f"{x/1e6:.4f}°E" if x > 0 else f"{-x/1e6:.4f}°W"

def fmt_lat(y, pos=None):
    return f"{y/1e6:.4f}°N" if y > 0 else f"{-y/1e6:.4f}°S"

# ============================================================
# Figure 1: 研究区概况 + 路网图
# ============================================================
print("\n[Fig 1] 研究区概况...")
fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# 1a: 路网分布图
ax = axes[0]
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.3, alpha=0.6)
gdf_proj.plot(ax=ax, column='population', cmap='YlOrRd',
              markersize=gdf_proj['population']/300+5, alpha=0.8,
              edgecolors='white', linewidths=0.3, legend=False)
ax.set_xlim(road_proj.total_bounds[0]-500, road_proj.total_bounds[2]+500)
ax.set_ylim(road_proj.total_bounds[1]-500, road_proj.total_bounds[3]+500)
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_title('(a) Nanshan District Road Network & Community Distribution',
              fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2, linestyle='--')

# 1b: 小区人口分布
ax = axes[1]
pop = gdf_proj['population'].values
cmap_pop = mcolors.LinearSegmentedColormap.from_list('pop', ['#fff7ec', '#fc8d59', '#d7301f'])
pop_norm = mcolors.Normalize(vmin=pop.min(), vmax=pop.max())
sc = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                c=pop, cmap=cmap_pop, s=pop/200+10,
                alpha=0.85, edgecolors='white', linewidths=0.4,
                norm=pop_norm)
plt.colorbar(sc, ax=ax, shrink=0.7, label='Population')
ax.set_xlim(road_proj.total_bounds[0]-500, road_proj.total_bounds[2]+500)
ax.set_ylim(road_proj.total_bounds[1]-500, road_proj.total_bounds[3]+500)
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_title('(b) Community Population Distribution', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2, linestyle='--')

# 标注小区数量和人口
total_pop = gdf['population'].sum()
ax.text(0.02, 0.98, f'Communities: {len(gdf)}\nTotal Pop: {total_pop/1e6:.2f}M',
        transform=ax.transAxes, fontsize=10, verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.suptitle('Figure 1: Study Area Overview — Nanshan District, Shenzhen',
             fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p7_fig1_study_area.png", dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p7_fig1_study_area.png")

# ============================================================
# Figure 2: 日间 vs 夜间可达性
# ============================================================
print("\n[Fig 2] 日间vs夜间可达性...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# 2a: 散点图
ax = axes[0]
day = gdf['A_day_norm'].values
night = gdf['A_night_norm'].values
pop = gdf['population'].values

sc = ax.scatter(day, night, c=pop, cmap='YlOrRd', s=pop/200+10,
                alpha=0.8, edgecolors='white', linewidths=0.4)
ax.plot([0, 1], [0, 1], 'k--', alpha=0.3, linewidth=1)
ax.set_xlabel('Day Accessibility (Normalized 2SFCA)')
ax.set_ylabel('Night Accessibility (Normalized 2SFCA)')
ax.set_title('(a) Day vs Night Accessibility', fontweight='bold')
ax.grid(True, alpha=0.3)

# 标注TPI极端小区
extreme_high = gdf.nlargest(3, 'TPI')
extreme_low = gdf.nsmallest(3, 'TPI')
for _, row in extreme_high.iterrows():
    ax.annotate(f"ID{int(row['community_id'])}\nTPI:{row['TPI']:.0f}%",
                (row['A_day_norm'], row['A_night_norm']),
                fontsize=8, color='darkred', fontweight='bold')
for _, row in extreme_low.iterrows():
    ax.annotate(f"ID{int(row['community_id'])}\nTPI:{row['TPI']:.0f}%",
                (row['A_day_norm'], row['A_night_norm']),
                fontsize=8, color='darkgreen')

# 填充区域
ax.fill_between([0, 1], [0, 1], [1, 1], alpha=0.1, color='red', label='Night > Day')
ax.fill_between([0, 1], [0, 0], [0, 1], alpha=0.1, color='green', label='Day > Night')
ax.legend(fontsize=9)

# 添加colorbar
cbar = plt.colorbar(sc, ax=ax, shrink=0.7)
cbar.set_label('Population', fontsize=10)

# 2b: TPI分布
ax = axes[1]
tpi = gdf['TPI'].values
colors = ['#1a9850' if t < 0 else '#f46d43' if t < 50 else '#d73027' for t in tpi]
n, bins, patches = ax.hist(tpi, bins=35, color='steelblue', alpha=0.75, edgecolor='white')
for i, patch in enumerate(patches):
    bin_center = (bins[i] + bins[i+1]) / 2
    if bin_center < 0:
        patch.set_facecolor('#1a9850')
    elif bin_center < 50:
        patch.set_facecolor('#f46d43')
    else:
        patch.set_facecolor('#d73027')

ax.axvline(x=0, color='black', linestyle='--', linewidth=2, label='No gap')
ax.axvline(x=tpi.mean(), color='red', linestyle='-', linewidth=2, label=f'Mean: {tpi.mean():.1f}%')
ax.axvline(x=np.median(tpi), color='orange', linestyle='-', linewidth=1.5, label=f'Median: {np.median(tpi):.1f}%')
ax.set_xlabel('Time Poverty Index (TPI, %)')
ax.set_ylabel('Community Count')
ax.set_title('(b) TPI Distribution', fontweight='bold')
ax.legend(fontsize=9, loc='upper left')
ax.grid(True, alpha=0.3, axis='y')

# 添加统计注释
deprived = gdf[gdf['TPI'] > 5]
n_dep = len(deprived)
pop_dep = deprived['population'].sum()
ax.text(0.97, 0.95,
        f'Night-deprived: {n_dep}/{len(gdf)} ({100*n_dep/len(gdf):.1f}%)\nAffected pop: {pop_dep/1000:.0f}K ({100*pop_dep/total_pop:.1f}%)',
        transform=ax.transAxes, fontsize=10, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.suptitle('Figure 2: Day vs Night Accessibility Analysis',
             fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p7_fig2_day_night.png", dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p7_fig2_day_night.png")

# ============================================================
# Figure 3: 空间分布地图 (核心图)
# ============================================================
print("\n[Fig 3] 空间分布地图...")
fig, axes = plt.subplots(2, 2, figsize=(18, 16))

# 3a: 日间可达性
ax = axes[0, 0]
day_v = gdf_proj['A_day_norm'].values
sc1 = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                  c=day_v, cmap='RdYlGn', s=gdf_proj['population']/200+15,
                  alpha=0.85, edgecolors='white', linewidths=0.3,
                  vmin=0, vmax=day_v.max())
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.2, alpha=0.4)
plt.colorbar(sc1, ax=ax, shrink=0.6, label='Normalized Accessibility')
ax.set_xlim(road_proj.total_bounds[0]-300, road_proj.total_bounds[2]+300)
ax.set_ylim(road_proj.total_bounds[1]-300, road_proj.total_bounds[3]+300)
ax.set_title('(a) Day Accessibility (2SFCA)', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2)

# 3b: 夜间可达性
ax = axes[0, 1]
night_v = gdf_proj['A_night_norm'].values
sc2 = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                   c=night_v, cmap='RdYlGn', s=gdf_proj['population']/200+15,
                   alpha=0.85, edgecolors='white', linewidths=0.3,
                   vmin=0, vmax=day_v.max())
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.2, alpha=0.4)
plt.colorbar(sc2, ax=ax, shrink=0.6, label='Normalized Accessibility')
ax.set_xlim(road_proj.total_bounds[0]-300, road_proj.total_bounds[2]+300)
ax.set_ylim(road_proj.total_bounds[1]-300, road_proj.total_bounds[3]+300)
ax.set_title('(b) Night Accessibility (2SFCA)', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2)

# 3c: TPI空间分布
ax = axes[1, 0]
tpi_v = gdf_proj['TPI'].values
sc3 = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                   c=tpi_v, cmap=TPI_CMAP, s=gdf_proj['population']/200+15,
                   alpha=0.85, edgecolors='white', linewidths=0.3,
                   norm=TPI_NORM)
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.2, alpha=0.4)
cbar3 = plt.colorbar(sc3, ax=ax, shrink=0.6)
cbar3.set_label('TPI (%)', fontsize=10)
ax.set_xlim(road_proj.total_bounds[0]-300, road_proj.total_bounds[2]+300)
ax.set_ylim(road_proj.total_bounds[1]-300, road_proj.total_bounds[3]+300)
ax.set_title('(c) Time Poverty Index (TPI)', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2)

# 标注严重时间贫困小区
severe = gdf_proj[gdf_proj['TPI'] > 50]
ax.scatter(severe.geometry.x, severe.geometry.y,
           facecolors='none', edgecolors='darkred', s=250, linewidths=2, label='Severe (TPI>50%)')
ax.scatter(severe.geometry.x, severe.geometry.y,
           facecolors='darkred', s=30, alpha=0.5)
for _, row in severe.iterrows():
    ax.annotate(f"C{int(row['community_id'])}\n{row['TPI']:.0f}%",
                (row.geometry.x+200, row.geometry.y+200), fontsize=7, color='darkred', fontweight='bold')
ax.legend(fontsize=9, loc='upper left')

# 3d: 人口加权TPI热力
ax = axes[1, 1]
pw_tpi = gdf_proj['population'] * gdf_proj['TPI']
tpi_abs = gdf_proj['TPI'].abs()
cmap_abs = mcolors.LinearSegmentedColormap.from_list('saii', ['#1a9850', '#ffffbf', '#d73027'])
sc4 = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                   c=pw_tpi, cmap=cmap_abs, s=gdf_proj['population']/200+15,
                   alpha=0.85, edgecolors='white', linewidths=0.3,
                   vmin=-30000, vmax=30000)
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.2, alpha=0.4)
cbar4 = plt.colorbar(sc4, ax=ax, shrink=0.6)
cbar4.set_label('Pop × TPI', fontsize=10)
ax.set_xlim(road_proj.total_bounds[0]-300, road_proj.total_bounds[2]+300)
ax.set_ylim(road_proj.total_bounds[1]-300, road_proj.total_bounds[3]+300)
ax.set_title('(d) Population-Weighted TPI\n(Large dot = More people affected)', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.2)

plt.suptitle('Figure 3: Spatial Accessibility Distribution\n(Nanshan District, Shenzhen)',
             fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p7_fig3_spatial.png", dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p7_fig3_spatial.png")

# ============================================================
# Figure 4: 夜间服务供需分析
# ============================================================
print("\n[Fig 4] 夜间服务供需分析...")
poi_df = pd.read_csv(f"{BASE}/osm_data/nanshan_poi_integrated_v3.csv", low_memory=False)

fig, axes = plt.subplots(1, 2, figsize=(18, 7))

# 4a: 设施夜间服务覆盖率
ax = axes[0]
type_stats = poi_df.groupby('facility_type').agg(
    total=('night_service_final', 'count'),
    night=('night_service_final', 'sum')
).reset_index()
type_stats['night_rate'] = type_stats['night'] / type_stats['total'] * 100
type_stats = type_stats.sort_values('night_rate')

colors_fc = []
for _, row in type_stats.iterrows():
    r = row['night_rate']
    if r < 10: colors_fc.append('#d73027')
    elif r < 30: colors_fc.append('#f46d43')
    elif r < 50: colors_fc.append('#fdae61')
    else: colors_fc.append('#1a9850')

y_pos = np.arange(len(type_stats))
bars = ax.barh(y_pos, type_stats['night_rate'], color=colors_fc, alpha=0.85, height=0.7)
for i, (_, row) in enumerate(type_stats.iterrows()):
    label = f"  {row['night_rate']:.1f}% ({int(row['night']):,}/{int(row['total']):,})"
    ax.text(row['night_rate'] + 1, i, label, va='center', fontsize=9, color='#333333')

ax.set_yticks(y_pos)
ax.set_yticklabels(type_stats['facility_type'], fontsize=10)
ax.set_xlabel('Night Service Rate (%)')
ax.set_title('(a) Night Service Coverage by Facility Type', fontweight='bold', fontsize=13)
ax.axvline(x=50, color='gray', linestyle='--', alpha=0.5, linewidth=1)
ax.axvline(x=30, color='orange', linestyle='--', alpha=0.5, linewidth=1)
ax.text(50, -1, '50%', fontsize=8, color='gray', ha='left')
ax.text(30, -1, '30%', fontsize=8, color='orange', ha='left')
ax.set_xlim(0, 105)
ax.grid(axis='x', alpha=0.3)

# 4b: SAII排名
ax = axes[1]
top_saii = gdf.nlargest(15, 'SAII').sort_values('SAII')
colors_saii = ['#d73027' if s > 0.04 else '#f46d43' if s > 0.02 else '#fdae61' for s in top_saii['SAII']]
bars = ax.barh(np.arange(len(top_saii)), top_saii['SAII'], color=colors_saii, alpha=0.85, height=0.7)
ax.set_yticks(np.arange(len(top_saii)))
labels = [f"ID{int(r['community_id'])} (Pop:{int(r['population']):,})" for _, r in top_saii.iterrows()]
ax.set_yticklabels(labels, fontsize=9)
ax.set_xlabel('SAII Score')
ax.set_title('(b) Top 15 Accessibility Illusion Communities\n(SAII = Day Access × |TPI|)', fontweight='bold', fontsize=13)
ax.grid(axis='x', alpha=0.3)
ax.invert_yaxis()

for i, (_, row) in enumerate(top_saii.iterrows()):
    ax.text(row['SAII'] + 0.001, i,
            f"SAII:{row['SAII']:.3f}  TPI:{row['TPI']:.1f}%  Day:{row['A_day_norm']:.3f}",
            va='center', fontsize=8, color='#333333')

plt.suptitle('Figure 4: Night Service Supply-Demand Analysis',
             fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p7_fig4_night_service.png", dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p7_fig4_night_service.png")

# ============================================================
# Figure 5: 综合研究结论图
# ============================================================
print("\n[Fig 5] 综合研究结论...")
fig = plt.figure(figsize=(20, 14))

# 5a: TPI空间地图(主图)
ax1 = fig.add_subplot(2, 3, (1, 4))
sc = ax1.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                c=gdf_proj['TPI'], cmap=TPI_CMAP, s=gdf_proj['population']/200+20,
                alpha=0.85, edgecolors='white', linewidths=0.5, norm=TPI_NORM)
road_proj.plot(ax=ax1, color='#cccccc', linewidth=0.15, alpha=0.35)
cbar = plt.colorbar(sc, ax=ax1, shrink=0.8, pad=0.02)
cbar.set_label('TPI (%)', fontsize=12)
ax1.set_xlim(road_proj.total_bounds[0]-200, road_proj.total_bounds[2]+200)
ax1.set_ylim(road_proj.total_bounds[1]-200, road_proj.total_bounds[3]+200)
ax1.set_xlabel('Longitude', fontsize=11)
ax1.set_ylabel('Latitude', fontsize=11)
ax1.set_title('Time Poverty Index (TPI) Spatial Distribution', fontweight='bold', fontsize=14)
ax1.grid(True, alpha=0.15)

# 标注严重小区
severe2 = gdf_proj[gdf_proj['TPI'] > 100]
for _, row in severe2.iterrows():
    ax1.scatter(row.geometry.x, row.geometry.y, facecolors='none', edgecolors='darkred', s=300, linewidths=2.5)
    ax1.annotate(f"C{int(row['community_id'])}\n{row['population']:,}pop\nTPI:{row['TPI']:.0f}%",
                 (row.geometry.x+200, row.geometry.y+200), fontsize=7.5, color='darkred', fontweight='bold')

# 添加图例
legend_elements = [
    mpatches.Patch(facecolor='#d73027', label='Severe Deprivation (TPI>50%)'),
    mpatches.Patch(facecolor='#f46d43', label='Moderate (20-50%)'),
    mpatches.Patch(facecolor='#fdae61', label='Mild (5-20%)'),
    mpatches.Patch(facecolor='#fee08b', label='None (-5~5%)'),
    mpatches.Patch(facecolor='#91cf60', label='Night Adv. (-20~-5%)'),
    mpatches.Patch(facecolor='#1a9850', label='Strong Night Adv. (<-20%)'),
]
ax1.legend(handles=legend_elements, fontsize=9, loc='upper left', framealpha=0.9)

# 5b: TPI等级人口分布饼图
ax2 = fig.add_subplot(2, 3, 2)
level_order = ['4-Severe', '3-Moderate', '2-Mild', '1-None', '0-NightAdv']
level_pop_sum = []
level_labels_short = []
level_colors = ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#1a9850']
for lv in level_order:
    mask = gdf['TPI_level'] == lv
    level_pop_sum.append(gdf[mask]['population'].sum())
    short_names = {'4-Severe': 'Severe\nDepriv.', '3-Moderate': 'Moderate', '2-Mild': 'Mild', '1-None': 'No Sig.', '0-NightAdv': 'Night\nAdv.'}
    level_labels_short.append(short_names.get(lv, lv))

wedges, texts, autotexts = ax2.pie(level_pop_sum, labels=level_labels_short, autopct='%1.1f%%',
                                    colors=level_colors, startangle=90, pctdistance=0.75,
                                    textprops={'fontsize': 9})
for t in autotexts:
    t.set_fontsize(9)
    t.set_fontweight('bold')
ax2.set_title('Population Distribution by TPI Level', fontweight='bold', fontsize=12)
# 添加说明
total_affected = sum(level_pop_sum[:3])  # Severe+Moderate+Mild
ax2.text(0, -1.5, f'Night-deprived pop: {total_affected/1000:.0f}K / {total_pop/1000:.0f}K = {100*total_affected/total_pop:.1f}%',
         fontsize=9, ha='center')

# 5c: 日间vs夜间可达性变化
ax3 = fig.add_subplot(2, 3, 3)
sorted_gdf = gdf.sort_values('A_day_norm')
x_idx = np.arange(len(sorted_gdf))
ax3.fill_between(x_idx, sorted_gdf['A_day_norm'], alpha=0.25, color='green', label='Day Accessibility')
ax3.fill_between(x_idx, sorted_gdf['A_night_norm'], alpha=0.25, color='blue', label='Night Accessibility')
ax3.plot(x_idx, sorted_gdf['A_day_norm'], color='green', linewidth=1.5, alpha=0.9)
ax3.plot(x_idx, sorted_gdf['A_night_norm'], color='blue', linewidth=1.5, alpha=0.9)
ax3.set_xlabel('Community Rank (by Day Accessibility)', fontsize=10)
ax3.set_ylabel('Normalized Accessibility', fontsize=10)
ax3.set_title('Accessibility Gap Profile', fontweight='bold', fontsize=12)
ax3.legend(fontsize=9)
ax3.grid(True, alpha=0.3)

# 5d: 小区类型TPI
ax4 = fig.add_subplot(2, 3, 5)
if 'community_type' in gdf.columns:
    type_tpi = gdf.groupby('community_type').apply(
        lambda x: pd.Series({
            'wmean_tpi': (x['TPI'] * x['population']).sum() / x['population'].sum(),
            'total_pop': x['population'].sum(),
            'count': len(x)
        })
    ).reset_index().sort_values('wmean_tpi')
    colors_ct = ['#d73027' if v < -30 else '#f46d43' if v < 0 else '#1a9850' for v in type_tpi['wmean_tpi']]
    bars = ax4.barh(type_tpi['community_type'], type_tpi['wmean_tpi'], color=colors_ct, alpha=0.85, height=0.6)
    for i, (_, row) in enumerate(type_tpi.iterrows()):
        va = 'bottom' if row['wmean_tpi'] >= 0 else 'top'
        offset = 3 if row['wmean_tpi'] >= 0 else -3
        ax4.text(row['wmean_tpi'] + offset, i, f"{row['wmean_tpi']:.1f}% ({int(row['total_pop']/1000):,}K)", va=va, fontsize=9)
    ax4.axvline(x=0, color='black', linestyle='--', alpha=0.5)
    ax4.set_xlabel('Population-Weighted Mean TPI (%)', fontsize=10)
    ax4.set_title('TPI by Community Type', fontweight='bold', fontsize=12)
    ax4.grid(axis='x', alpha=0.3)

# 5e: 设施缺口
ax5 = fig.add_subplot(2, 3, 6)
top_gap = type_stats.nsmallest(8, 'night_rate')
gap_vals = 100 - top_gap['night_rate']
colors_gap = ['#d73027' if v > 80 else '#f46d43' if v > 50 else '#fdae61' for v in gap_vals]
bars = ax5.barh(np.arange(len(top_gap)), gap_vals, color=colors_gap, alpha=0.85, height=0.6)
ax5.set_yticks(np.arange(len(top_gap)))
ax5.set_yticklabels(top_gap['facility_type'], fontsize=9)
ax5.set_xlabel('Night Service Gap (%)', fontsize=10)
ax5.set_title('Critical Night Service Gaps', fontweight='bold', fontsize=12)
ax5.grid(axis='x', alpha=0.3)
ax5.set_xlim(0, 105)
for i, (_, row) in enumerate(top_gap.iterrows()):
    ax5.text(100-row['night_rate']+1, i, f"{100-row['night_rate']:.1f}%", va='center', fontsize=8)

plt.suptitle('Figure 5: Accessibility Illusion Analysis — Nanshan District, Shenzhen\n'
             f'(Real Population: {total_pop/1e6:.2f}M | Network: {len(road_ns):,} roads, 28.0 km/km² | '
             f'Day POI: {len(poi_df):,} | Night POI: {poi_df["night_service_final"].sum():,})',
             fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p7_fig5_conclusion.png", dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p7_fig5_conclusion.png")

# ============================================================
# 输出关键统计
# ============================================================
print("\n" + "=" * 70)
print("研究级可视化完成")
print("=" * 70)
print(f"\n输出文件:")
print(f"  Fig1: p7_fig1_study_area.png      - 研究区概况")
print(f"  Fig2: p7_fig2_day_night.png       - 日夜间对比")
print(f"  Fig3: p7_fig3_spatial.png         - 空间分布")
print(f"  Fig4: p7_fig4_night_service.png   - 夜间服务")
print(f"  Fig5: p7_fig5_conclusion.png      - 综合结论")

print(f"\n关键数据:")
print(f"  小区: {len(gdf)} | 人口: {total_pop/1e6:.2f}M")
print(f"  路网: {len(road_ns):,}条 | 密度: 28.0 km/km²")
print(f"  POI: {len(poi_df):,} (日) / {poi_df['night_service_final'].sum():,} (夜)")
print(f"  TPI: 均值{gdf['TPI'].mean():.1f}% | 中位数{np.median(gdf['TPI']):.1f}%")
print(f"  受影响人口: {total_affected/1000:.0f}K ({100*total_affected/total_pop:.1f}%)")

print("\n*** P7b COMPLETE ***")
