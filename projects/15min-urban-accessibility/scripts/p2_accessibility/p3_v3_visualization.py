# -*- coding: utf-8 -*-
"""
P3-V3: 可达性幻觉分析可视化 - 使用真实人口数据
生成6幅图表，展示南山区15分钟城市的时间贫困现象
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches
import geopandas as gpd
from shapely.geometry import Point
import contextily as ctx
import adjustText as aT

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# 中文字体
plt.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'SimSun', 'WenQuanYi Micro Hei', 'Noto Sans CJK SC']
plt.rcParams['axes.unicode_minus'] = False

# 颜色方案
RED_PALETTE = ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b']
BLUE_PALETTE = ['#fff5eb', '#fee6ce', '#fdd0a2', '#fdae6b', '#fd8d3c', '#f16913', '#d94801', '#a63603', '#7f2704']

def create_custom_cmap(low_color='#d73027', mid_color='#ffffbf', high_color='#1a9850'):
    cmap = mcolors.LinearSegmentedColormap.from_list('custom', [low_color, mid_color, high_color])
    return cmap

print("="*70)
print("P3-V3: 可达性幻觉可视化 - 真实人口数据版")
print("="*70)

# ============================================================
# 加载数据
# ============================================================
print("\n[1] Loading data...")
results = pd.read_csv(f"{BASE}/p2_v3_results.csv")
print(f"Communities: {len(results)}, Total pop: {results['population'].sum():,}")

# 南山区底图
shp_path = f"{BASE}/osm_data/nanshan_district.shp"
if os.path.exists(shp_path):
    ns_gdf = gpd.read_file(shp_path)
elif os.path.exists(f"{BASE}/osm_data/nanshan_area.geojson"):
    ns_gdf = gpd.read_file(f"{BASE}/osm_data/nanshan_area.geojson")
else:
    ns_gdf = None
    print("[WARN] No boundary file found, using scatter plot")

# ============================================================
# 图1: 日间 vs 夜间可达性散点图
# ============================================================
print("\n[2] Creating Figure 1: Day vs Night accessibility scatter...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# 左: 散点图
ax1 = axes[0]
pop = results['population'].values
day = results['A_i_2sfca_norm_day'].values
night = results['A_i_2sfca_norm_night'].values

scatter = ax1.scatter(day, night, c=pop, cmap='YlOrRd', s=pop/200+10, alpha=0.7, edgecolors='white', linewidths=0.5)
ax1.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='y=x')
ax1.set_xlabel('Day Accessibility (2SFCA)', fontsize=12)
ax1.set_ylabel('Night Accessibility (2SFCA)', fontsize=12)
ax1.set_title('Day vs Night Accessibility\n(Color = Population, Size = Population)', fontsize=13)
cbar = plt.colorbar(scatter, ax=ax1, shrink=0.8)
cbar.set_label('Population', fontsize=10)

# 标注极值点
for idx in results.nlargest(3, 'TPI').index:
    row = results.loc[idx]
    ax1.annotate(f"{row['community_id']}\nTPI:{row['TPI']:.1f}%",
                  (row['A_i_2sfca_norm_day'], row['A_i_2sfca_norm_night']),
                  fontsize=7, color='red', fontweight='bold')

ax1.legend()
ax1.grid(True, alpha=0.3)

# 右: TPI分布直方图
ax2 = axes[1]
tpi = results['TPI'].values
colors = ['#1a9850' if t < 0 else '#d73027' for t in tpi]
ax2.hist(tpi, bins=30, color='steelblue', alpha=0.7, edgecolor='white')
ax2.axvline(x=0, color='black', linestyle='--', linewidth=1.5, label='No gap')
ax2.axvline(x=tpi.mean(), color='red', linestyle='-', linewidth=2, label=f'Mean: {tpi.mean():.1f}%')
ax2.set_xlabel('TPI (%)', fontsize=12)
ax2.set_ylabel('Community Count', fontsize=12)
ax2.set_title('Time Poverty Index Distribution\n(Negative = Night Advantage)', fontsize=13)
ax2.legend()
ax2.grid(True, alpha=0.3)

# 添加注释
deprived = results[results['TPI'] > 5]
n_deprived = len(deprived)
n_total = len(results)
ax2.text(0.97, 0.95, f'Night-deprived communities:\n{n_deprived} / {n_total} ({100*n_deprived/n_total:.1f}%)\nTotal affected: {deprived["population"].sum():,}',
          transform=ax2.transAxes, fontsize=10, verticalalignment='top', horizontalalignment='right',
          bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_day_night_comparison.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_day_night_comparison.png")

# ============================================================
# 图2: 空间分布图
# ============================================================
print("\n[3] Creating Figure 2: Spatial distribution...")
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

# 创建地理数据
geometry = [Point(xy) for xy in zip(results['lng'], results['lat'])]
gdf = gpd.GeoDataFrame(results, geometry=geometry, crs='EPSG:4326')

# 南山区底图
if ns_gdf is not None:
    try:
        ns_gdf = ns_gdf.to_crs('EPSG:3857')
        gdf_proj = gdf.to_crs('EPSG:3857')
        has_basemap = True
    except:
        has_basemap = False
        gdf_proj = gdf
else:
    has_basemap = False
    gdf_proj = gdf

# 2a: 日间可达性
ax = axes[0, 0]
day = results['A_i_2sfca_norm_day'].values
if ns_gdf is not None:
    try:
        ns_gdf.plot(ax=ax, color='whitesmoke', edgecolor='lightgray', alpha=0.5)
    except:
        pass
scatter = ax.scatter(results['lng'], results['lat'], c=day, cmap='RdYlGn', s=results['population']/200+15, alpha=0.8, edgecolors='white', linewidths=0.3, vmin=0, vmax=day.max())
ax.set_title('Day Accessibility (2SFCA)\n(Size = Population)', fontsize=12, fontweight='bold')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
plt.colorbar(scatter, ax=ax, shrink=0.6, label='Normalized Accessibility')

# 2b: 夜间可达性
ax = axes[0, 1]
night = results['A_i_2sfca_norm_night'].values
if ns_gdf is not None:
    try:
        ns_gdf.plot(ax=ax, color='whitesmoke', edgecolor='lightgray', alpha=0.5)
    except:
        pass
scatter = ax.scatter(results['lng'], results['lat'], c=night, cmap='RdYlGn', s=results['population']/200+15, alpha=0.8, edgecolors='white', linewidths=0.3, vmin=0, vmax=day.max())
ax.set_title('Night Accessibility (2SFCA)\n(Size = Population)', fontsize=12, fontweight='bold')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
plt.colorbar(scatter, ax=ax, shrink=0.6, label='Normalized Accessibility')

# 2c: TPI空间分布
ax = axes[1, 0]
tpi = results['TPI'].values
if ns_gdf is not None:
    try:
        ns_gdf.plot(ax=ax, color='whitesmoke', edgecolor='lightgray', alpha=0.5)
    except:
        pass
cmap_div = create_custom_cmap()
scatter = ax.scatter(results['lng'], results['lat'], c=tpi, cmap=cmap_div, s=results['population']/200+15, alpha=0.8, edgecolors='white', linewidths=0.3, vmin=-60, vmax=60)
ax.set_title('Time Poverty Index (TPI) Spatial Distribution\n(Negative = Night Advantage, Positive = Night Deprivation)', fontsize=12, fontweight='bold')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
cbar = plt.colorbar(scatter, ax=ax, shrink=0.6)
cbar.set_label('TPI (%)', fontsize=10)

# 标注严重时间贫困小区
severe = results[results['TPI'] > 30]
if len(severe) > 0:
    ax.scatter(severe['lng'], severe['lat'], facecolors='none', edgecolors='red', s=100, linewidths=2, label='Severe Deprivation (TPI>30%)')
    for _, row in severe.iterrows():
        ax.annotate(f"C{int(row['community_id'])}", (row['lng'], row['lat']), fontsize=6, color='red')
    ax.legend(fontsize=8)

# 2d: 人口加权TPI热力图
ax = axes[1, 1]
pop_weighted_tpi = results['population'] * results['TPI']
if ns_gdf is not None:
    try:
        ns_gdf.plot(ax=ax, color='whitesmoke', edgecolor='lightgray', alpha=0.5)
    except:
        pass
cmap_div2 = create_custom_cmap('#d73027', '#ffffbf', '#1a9850')
scatter = ax.scatter(results['lng'], results['lat'], c=pop_weighted_tpi, cmap=cmap_div2, s=results['population']/200+15, alpha=0.8, edgecolors='white', linewidths=0.3, vmin=-30000, vmax=30000)
ax.set_title('Population-Weighted TPI\n(Large dots = More people affected)', fontsize=12, fontweight='bold')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
cbar = plt.colorbar(scatter, ax=ax, shrink=0.6)
cbar.set_label('Pop × TPI', fontsize=10)

plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_spatial_distribution.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_spatial_distribution.png")

# ============================================================
# 图3: 分类型夜间服务覆盖
# ============================================================
print("\n[4] Creating Figure 3: Night service by facility type...")
fig, ax = plt.subplots(figsize=(14, 8))

# 读取POI数据
poi_df = pd.read_csv(f"{BASE}/osm_data/nanshan_poi_integrated_v3.csv", low_memory=False)
type_night = poi_df.groupby('facility_type').agg(
    total=('night_service_final', 'count'),
    night=('night_service_final', 'sum')
).reset_index()
type_night['night_rate'] = type_night['night'] / type_night['total'] * 100
type_night = type_night.sort_values('night_rate')

y_pos = np.arange(len(type_night))
bars = ax.barh(y_pos, type_night['night_rate'], color=['#d73027' if r < 10 else '#fdae6b' if r < 30 else '#1a9850' for r in type_night['night_rate']], alpha=0.85)

for i, (idx, row) in enumerate(type_night.iterrows()):
    ax.text(row['night_rate'] + 0.5, i, f"{row['night_rate']:.1f}% ({row['night']:,}/{row['total']:,})", va='center', fontsize=9, color='#333333')

ax.set_yticks(y_pos)
ax.set_yticklabels(type_night['facility_type'])
ax.set_xlabel('Night Service Rate (%)', fontsize=12)
ax.set_title('Night Service Coverage by Facility Type\n(Nanshan District, Shenzhen)', fontsize=14, fontweight='bold')
ax.axvline(x=50, color='gray', linestyle='--', alpha=0.5, label='50% threshold')
ax.axvline(x=30, color='orange', linestyle='--', alpha=0.5, label='30% threshold')
ax.legend(fontsize=9)
ax.grid(axis='x', alpha=0.3)
ax.set_xlim(0, 105)

plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_night_service_coverage.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_night_service_coverage.png")

# ============================================================
# 图4: 设施类型 × 小区类型 夜间服务供需分析
# ============================================================
print("\n[5] Creating Figure 4: Supply-demand analysis...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# 左: 小区类型TPI分布
ax = axes[0]
comm_pop = pd.read_csv(f"{BASE}/osm_data/nanshan_communities_real_population.csv")
comm_pop = comm_pop.rename(columns={'id': 'community_id'})
merged = results.merge(comm_pop[['community_id', 'community_type']], on='community_id', how='left')

type_tpi = []
for ct in merged['community_type'].dropna().unique():
    sub = merged[merged['community_type'] == ct]
    if len(sub) > 0:
        w_mean = (sub['TPI'] * sub['population']).sum() / sub['population'].sum()
        type_tpi.append({'type': ct, 'weighted_mean_tpi': w_mean, 'mean_tpi': sub['TPI'].mean(), 'count': len(sub), 'total_pop': sub['population'].sum()})

type_df = pd.DataFrame(type_tpi).sort_values('weighted_mean_tpi')
colors = ['#1a9850' if t < 0 else '#fdae6b' if t < 20 else '#d73027' for t in type_df['weighted_mean_tpi']]
bars = ax.barh(type_df['type'], type_df['weighted_mean_tpi'], color=colors, alpha=0.85)
for i, (idx, row) in enumerate(type_df.iterrows()):
    label = f"{row['weighted_mean_tpi']:.1f}% ({row['total_pop']:,})"
    ax.text(row['weighted_mean_tpi'] + 0.5 if row['weighted_mean_tpi'] >= 0 else row['weighted_mean_tpi'] - 0.5, i, label, va='center', ha='left' if row['weighted_mean_tpi'] >= 0 else 'right', fontsize=9)

ax.set_xlabel('Population-Weighted Mean TPI (%)', fontsize=11)
ax.set_title('TPI by Community Type\n(Population-Weighted)', fontsize=12, fontweight='bold')
ax.axvline(x=0, color='black', linestyle='--', alpha=0.5)
ax.grid(axis='x', alpha=0.3)

# 右: 供需缺口分析
ax = axes[1]
# 统计夜间最缺乏的设施类型
night_supply = poi_df.groupby('facility_type')['night_service_final'].sum()
total_supply = poi_df.groupby('facility_type')['night_service_final'].count()
night_gap = (total_supply - night_supply) / total_supply * 100

# 按gap排序
gap_df = pd.DataFrame({'facility_type': night_gap.index, 'gap_pct': night_gap.values})
gap_df = gap_df.sort_values('gap_pct', ascending=False).head(8)

x = np.arange(len(gap_df))
width = 0.6
colors_gap = ['#d73027' if v > 80 else '#fdae6b' if v > 50 else '#fee08b' for v in gap_df['gap_pct']]
bars = ax.bar(x, gap_df['gap_pct'], color=colors_gap, alpha=0.85, width=width)
ax.set_xticks(x)
ax.set_xticklabels(gap_df['facility_type'], rotation=45, ha='right', fontsize=10)
ax.set_ylabel('Service Gap (%)', fontsize=11)
ax.set_title('Top Night Service Gaps\n(1 - Night Service Rate)', fontsize=12, fontweight='bold')
ax.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='Severe gap (>80%)')
ax.axhline(y=50, color='orange', linestyle='--', alpha=0.5, label='Moderate gap (>50%)')
ax.legend(fontsize=8)
ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 105)

for i, (idx, row) in enumerate(gap_df.iterrows()):
    ax.text(i, row['gap_pct'] + 1, f"{row['gap_pct']:.1f}%", ha='center', fontsize=9, color='#333333')

plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_supply_demand_analysis.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_supply_demand_analysis.png")

# ============================================================
# 图5: 研究结论综合图
# ============================================================
print("\n[6] Creating Figure 5: Research conclusion summary...")
fig = plt.figure(figsize=(18, 12))

# 5a: 南山区夜间服务"幻觉"地图
ax1 = fig.add_subplot(2, 2, 1)
cmap_div3 = create_custom_cmap('#d73027', '#ffffbf', '#1a9850')
if ns_gdf is not None:
    try:
        ns_gdf.plot(ax=ax1, color='#f0f0f0', edgecolor='lightgray', alpha=0.3)
    except:
        pass
scatter = ax1.scatter(results['lng'], results['lat'], c=results['TPI'], cmap=cmap_div3, s=results['population']/200+20, alpha=0.85, edgecolors='white', linewidths=0.5, vmin=-60, vmax=60)
ax1.set_title('Nanshan District: Time Poverty Index\n"Accessibility Illusion" Map', fontsize=13, fontweight='bold')
ax1.set_xlabel('Longitude')
ax1.set_ylabel('Latitude')
cbar = plt.colorbar(scatter, ax=ax1, shrink=0.7)
cbar.set_label('TPI (%)', fontsize=10)

# 严重时间贫困标注
severe = results[results['TPI'] > 20]
for _, row in severe.iterrows():
    ax1.scatter(row['lng'], row['lat'], facecolors='none', edgecolors='darkred', s=200, linewidths=2)
    ax1.annotate(f"C{int(row['community_id'])}\nPop:{row['population']:,}", (row['lng']+0.002, row['lat']+0.001), fontsize=7, color='darkred')

# 5b: TPI水平分布饼图
ax2 = fig.add_subplot(2, 2, 2)
level_counts = results['TPI_level'].value_counts()
level_colors = {
    '4-Severe Deprivation': '#d73027',
    '3-Moderate Deprivation': '#f46d43',
    '2-Mild Deprivation': '#fdae61',
    '1-No Significant': '#fee08b',
    '0-Night Advantage': '#1a9850'
}
pie_colors = [level_colors.get(l, '#999') for l in level_counts.index]
wedges, texts, autotexts = ax2.pie(level_counts.values, labels=level_counts.index, autopct='%1.1f%%', colors=pie_colors, startangle=90, pctdistance=0.75)
for t in autotexts:
    t.set_fontsize(9)
    t.set_fontweight('bold')
ax2.set_title('TPI Level Distribution\n(Community Count)', fontsize=13, fontweight='bold')

# 5c: 人口受影响分布
ax3 = fig.add_subplot(2, 2, 3)
level_pop = results.groupby('TPI_level').agg(
    count=('community_id', 'count'),
    population=('population', 'sum')
).reset_index()
level_order = ['4-Severe Deprivation', '3-Moderate Deprivation', '2-Mild Deprivation', '1-No Significant', '0-Night Advantage']
level_pop['TPI_level'] = pd.Categorical(level_pop['TPI_level'], categories=level_order, ordered=True)
level_pop = level_pop.sort_values('TPI_level')

bar_colors = [level_colors.get(l, '#999') for l in level_pop['TPI_level']]
bars = ax3.bar(range(len(level_pop)), level_pop['population']/1000, color=bar_colors, alpha=0.85, edgecolor='white', linewidth=1)
ax3.set_xticks(range(len(level_pop)))
ax3.set_xticklabels([l.replace('Deprivation', 'Dep.').replace('Advantage', 'Adv.').replace('Significant', 'Sig.') for l in level_pop['TPI_level']], rotation=30, ha='right', fontsize=9)
ax3.set_ylabel('Population (thousands)', fontsize=11)
ax3.set_title('Population by TPI Level\n(Affected Population)', fontsize=13, fontweight='bold')
for i, (idx, row) in enumerate(level_pop.iterrows()):
    ax3.text(i, row['population']/1000 + 3, f'{row["population"]/1000:.0f}K', ha='center', fontsize=9, fontweight='bold')
ax3.grid(axis='y', alpha=0.3)

# 5d: 日间vs夜间可达性变化
ax4 = fig.add_subplot(2, 2, 4)
results_sorted = results.sort_values('A_i_2sfca_norm_day')
x_range = range(len(results_sorted))
ax4.fill_between(x_range, results_sorted['A_i_2sfca_norm_day'], alpha=0.3, color='green', label='Day Accessibility')
ax4.fill_between(x_range, results_sorted['A_i_2sfca_norm_night'], alpha=0.3, color='blue', label='Night Accessibility')
ax4.plot(x_range, results_sorted['A_i_2sfca_norm_day'], color='green', linewidth=1, alpha=0.8)
ax4.plot(x_range, results_sorted['A_i_2sfca_norm_night'], color='blue', linewidth=1, alpha=0.8)
ax4.set_xlabel('Community Rank (by Day Accessibility)', fontsize=11)
ax4.set_ylabel('Normalized Accessibility', fontsize=11)
ax4.set_title('Day vs Night Accessibility Profile\n(Sorted by Day Accessibility)', fontsize=13, fontweight='bold')
ax4.legend(fontsize=10)
ax4.grid(True, alpha=0.3)

plt.suptitle('Shenzhen Nanshan: Accessibility Illusion Analysis\n(Real Population: 1.6M Residents | POI: 69,422)', fontsize=15, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_research_summary.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_research_summary.png")

# ============================================================
# 图6: 时空可达性幻觉指数 (SAII) 分析
# ============================================================
print("\n[7] Creating Figure 6: SAII analysis...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

# SAII = SAI × |TPI|
# SAI = 标准化可达性指数
sai = results['A_i_2sfca_norm_day']
tpi_abs = results['TPI'].abs()
results['SAII'] = sai * tpi_abs / 100

# 左: SAII分布
ax = axes[0]
saii = results['SAII'].values
cmap_saii = mcolors.LinearSegmentedColormap.from_list('saii', ['#1a9850', '#ffffbf', '#d73027'])
scatter = ax.scatter(results['lng'], results['lat'], c=saii, cmap=cmap_saii, s=results['population']/200+20, alpha=0.8, edgecolors='white', linewidths=0.3)
ax.set_title('Spatio-Temporal Accessibility Illusion Index (SAII)\nSAII = Day Accessibility × |TPI|', fontsize=12, fontweight='bold')
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
cbar = plt.colorbar(scatter, ax=ax, shrink=0.7)
cbar.set_label('SAII', fontsize=10)

# 标注高SAII小区
high_saii = results.nlargest(5, 'SAII')
for _, row in high_saii.iterrows():
    ax.annotate(f"C{int(row['community_id'])}", (row['lng']+0.002, row['lat']), fontsize=8, color='darkred', fontweight='bold')

# 右: SAII排名
ax = axes[1]
top_saii = results.nlargest(20, 'SAII')[['community_id', 'population', 'A_i_2sfca_norm_day', 'TPI', 'SAII']]
y_pos = np.arange(len(top_saii))
colors_saii = ['#d73027' if s > 0.03 else '#f46d43' if s > 0.02 else '#fdae61' for s in top_saii['SAII']]
bars = ax.barh(y_pos, top_saii['SAII'], color=colors_saii, alpha=0.85)
ax.set_yticks(y_pos)
ax.set_yticklabels([f"C{int(r['community_id'])} (Pop:{r['population']:,})" for _, r in top_saii.iterrows()], fontsize=9)
ax.set_xlabel('SAII Score', fontsize=11)
ax.set_title('Top 20 "Accessibility Illusion" Communities\n(High SAII = High Day Access + Large TPI Gap)', fontsize=12, fontweight='bold')
ax.invert_yaxis()
ax.grid(axis='x', alpha=0.3)

for i, (idx, row) in enumerate(top_saii.iterrows()):
    ax.text(row['SAII'] + 0.001, i, f"SAII:{row['SAII']:.3f} TPI:{row['TPI']:.1f}%", va='center', fontsize=8)

plt.tight_layout()
fig.savefig(f"{BASE}/p3_v3_saii_analysis.png", dpi=150, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p3_v3_saii_analysis.png")

print("\n" + "="*70)
print("All visualizations complete!")
print("="*70)
print("Output files:")
print(f"  1. p3_v3_day_night_comparison.png - Day vs Night comparison")
print(f"  2. p3_v3_spatial_distribution.png - Spatial distribution maps")
print(f"  3. p3_v3_night_service_coverage.png - Night service coverage")
print(f"  4. p3_v3_supply_demand_analysis.png - Supply-demand analysis")
print(f"  5. p3_v3_research_summary.png - Research summary")
print(f"  6. p3_v3_saii_analysis.png - SAII analysis")
print("\n*** P3-V3 COMPLETE ***")
