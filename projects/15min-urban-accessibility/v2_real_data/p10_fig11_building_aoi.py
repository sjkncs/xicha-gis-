# -*- coding: utf-8 -*-
"""
P10: Fig11 建筑AOI补充图表
==================================
基于南山区16,588栋建筑OSM数据，生成4张独立补充图:
  Fig11a: 建筑用途分类空间分布
  Fig11b: 建筑高度(楼层数)热力分布
  Fig11c: 高层建筑聚集与TPI剥夺叠加
  Fig11d: 建筑密度与社区可达性格局对比

运行: python p10_fig11_building_aoi.py
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches
from matplotlib.colors import Normalize
from scipy.stats import gaussian_kde

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT_DIR = os.path.join(BASE, "v2_real_data")

FONT_CJK = ['Source Han Sans SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
            'Microsoft YaHei', 'SimHei', 'PingFang SC', 'STHeiti']
plt.rcParams['font.family'] = FONT_CJK + ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 9
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 8
plt.rcParams['figure.titlesize'] = 13

print("=" * 70)
print("P10: Fig11 建筑AOI补充图表生成")
print("=" * 70)

# ================================================================
# 1. 加载数据
# ================================================================
print("\n[1] 加载数据...")

BDIR = os.path.join(BASE, "building_data")
bld_path = os.path.join(BDIR, "nanshan_buildings_v2.geojson")
bld = gpd.read_file(bld_path)
print(f"  楼栋数据: {len(bld)} 栋")
print(f"  CRS: {bld.crs}")

# 转换为WGS84 (EPSG:4326) 用于绘图
bld_wgs = bld.to_crs('EPSG:4326')

# 处理levels字段
def parse_levels(val):
    if pd.isna(val) or val == '' or val == ' ':
        return np.nan
    try:
        return float(val)
    except:
        return np.nan

bld_wgs['levels_num'] = bld_wgs['levels'].apply(parse_levels)
bld_wgs['levels_filled'] = bld_wgs['levels_num'].fillna(bld_wgs['levels_num'].median())

# 建筑用途归类
def classify_building(bt):
    if pd.isna(bt):
        return 'other'
    bt = str(bt).lower()
    if bt in ['house', 'detached']:
        return 'residential_low'
    elif bt in ['apartments', 'residential', 'dormitory']:
        return 'residential_mid'
    elif bt in ['commercial', 'retail', 'office']:
        return 'commercial'
    elif bt in ['industrial', 'warehouse']:
        return 'industrial'
    elif bt in ['public', 'government']:
        return 'public'
    elif bt in ['yes', 'building']:
        return 'unspecified'
    else:
        return 'other'

bld_wgs['btype_cat'] = bld_wgs['building'].apply(classify_building)

# 加载社区可达性结果
results = pd.read_csv(os.path.join(OUT_DIR, "p8_network_results.csv"))
print(f"  社区可达性: {len(results)} 个小区")

# 加载路网
road_shp = os.path.join(BASE, "osm_data", "nanshan_road_network.shp")
road_wgs = gpd.read_file(road_shp)
road_proj = road_wgs.to_crs('EPSG:3857')
print(f"  路网: {len(road_wgs)} 条边")

# 构建Web Mercator版建筑数据用于叠加分析
bld_proj = bld_wgs.to_crs('EPSG:3857')

# 为建筑分配最近的TPI值 (基于最近邻)
from scipy.spatial import cKDTree

bld_coords = np.array([bld_wgs.geometry.centroid.x.values,
                         bld_wgs.geometry.centroid.y.values]).T
comm_coords = np.array([results['lng'].values, results['lat'].values]).T

tree = cKDTree(comm_coords)
distances, indices = tree.query(bld_coords, k=1)
bld_wgs['nearest_tpi'] = results.iloc[indices]['TPI'].values
bld_wgs['nearest_community_id'] = results.iloc[indices]['community_id'].values

# 计算每个建筑群落单元(100m网格)密度
from shapely.geometry import box
bld_bounds = bld_wgs.total_bounds  # [minx, miny, maxx, maxy]
print(f"  研究区: [{bld_bounds[0]:.4f}, {bld_bounds[1]:.4f}] - [{bld_bounds[2]:.4f}, {bld_bounds[3]:.4f}]")

# 统计
print(f"\n建筑类型分布:")
print(bld_wgs['btype_cat'].value_counts().to_string())
print(f"\n楼层数统计:")
valid_lvls = bld_wgs['levels_num'].dropna()
print(f"  有效: {valid_lvls.notna().sum()} / {len(bld_wgs)}")
print(f"  均值: {valid_lvls.mean():.1f} 层, 最大: {valid_lvls.max():.0f} 层")

# ================================================================
# 2. Fig11a: 建筑用途分类空间分布
# ================================================================
print("\n[2] Fig11a: 建筑用途分类空间分布...")

fig, ax = plt.subplots(figsize=(14, 12))

# 背景: 路网
road_wgs.plot(ax=ax, color='#cccccc', linewidth=0.15, alpha=0.4)

# 颜色映射
BTYPE_COLORS = {
    'residential_low':   '#90EE90',   # 浅绿 - 低层住宅
    'residential_mid':   '#228B22',   # 深绿 - 中高层住宅
    'commercial':        '#4169E1',   # 蓝色 - 商业
    'industrial':         '#808080',   # 灰色 - 工业
    'public':            '#9932CC',   # 紫色 - 公共设施
    'unspecified':       '#D3D3D3',   # 浅灰 - 未分类
    'other':             '#F0E68C',   # 卡其 - 其他
}
BTYPE_LABELS = {
    'residential_low': '低层住宅 (house/detached)',
    'residential_mid': '中高层住宅 (apartments/dormitory)',
    'commercial': '商业/办公 (commercial/retail/office)',
    'industrial': '工业仓储 (industrial/warehouse)',
    'public': '公共设施 (public/government)',
    'unspecified': '未分类 (building=yes)',
    'other': '其他',
}

# 绘制建筑
for btype, color in BTYPE_COLORS.items():
    subset = bld_wgs[bld_wgs['btype_cat'] == btype]
    if len(subset) > 0:
        ax.scatter(subset.geometry.centroid.x, subset.geometry.centroid.y,
                   c=color, s=2.5, alpha=0.7, label=f"{BTYPE_LABELS[btype]} (n={len(subset):,})")

ax.set_xlim(bld_bounds[0] - 0.002, bld_bounds[2] + 0.002)
ax.set_ylim(bld_bounds[1] - 0.002, bld_bounds[3] + 0.002)
ax.set_xlabel('Longitude (WGS84)', fontsize=11)
ax.set_ylabel('Latitude (WGS84)', fontsize=11)
ax.set_title('(a) Building Use Type Spatial Distribution in Nanshan District',
             fontweight='bold', fontsize=13)
ax.legend(loc='upper left', fontsize=8, ncol=2, framealpha=0.9,
          title='Building Type', title_fontsize=9)
ax.grid(True, alpha=0.15, linestyle='--')
ax.set_aspect('equal')

plt.suptitle('Figure 11a: Building AOI Analysis — Use Type Classification\n'
             'Nanshan District, Shenzhen | Source: OpenStreetMap | Total: 16,588 buildings',
             fontsize=11, y=0.01)

fig.tight_layout(rect=[0, 0.03, 1, 0.97])
fig.savefig(os.path.join(OUT_DIR, "p8_fig11a_building_use_type.png"),
           dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p8_fig11a_building_use_type.png")

# ================================================================
# 3. Fig11b: 建筑高度热力分布
# ================================================================
print("\n[3] Fig11b: 建筑高度热力分布...")

fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# 左: 散点热力图
ax = axes[0]
valid_heights = bld_wgs[bld_wgs['levels_num'].notna()].copy()
valid_heights = valid_heights[valid_heights['levels_num'] > 0]

if len(valid_heights) > 50:
    x_pts = valid_heights.geometry.centroid.x.values
    y_pts = valid_heights.geometry.centroid.y.values
    z_pts = valid_heights['levels_num'].values

    # 2D KDE热力
    try:
        xy = np.vstack([x_pts, y_pts])
        kde = gaussian_kde(xy, weights=z_pts.clip(1, None))
        xi, yi = np.mgrid[x_pts.min():x_pts.max():100j, y_pts.min():y_pts.max():100j]
        zi = kde(np.vstack([xi.ravel(), yi.ravel()])).reshape(xi.shape)
        im = ax.contourf(xi, yi, zi, levels=30, cmap='YlOrRd', alpha=0.7)
    except:
        im = ax.scatter(x_pts, y_pts, c=z_pts, cmap='YlOrRd',
                       s=3, alpha=0.6, vmin=1, vmax=50)
else:
    im = ax.scatter(valid_heights.geometry.centroid.x,
                   valid_heights.geometry.centroid.y,
                   c=valid_heights['levels_num'],
                   cmap='YlOrRd', s=5, alpha=0.7)

road_wgs.plot(ax=ax, color='white', linewidth=0.1, alpha=0.3)

# 标注超高层建筑 (>30层)
super_tall = valid_heights[valid_heights['levels_num'] >= 30]
ax.scatter(super_tall.geometry.centroid.x, super_tall.geometry.centroid.y,
           facecolors='none', edgecolors='darkred', s=40, linewidths=1.5,
           label=f'Super High-rise (>=30F, n={len(super_tall)})')
for _, row in super_tall.nlargest(5, 'levels_num').iterrows():
    name = str(row.get('name', ''))[:8] if row.get('name', '') else 'N/A'
    lvls = row['levels_num']
    ax.annotate(f"{name}\n{int(lvls)}F",
                (row.geometry.centroid.x, row.geometry.centroid.y),
                fontsize=7, color='darkred')

ax.set_xlim(bld_bounds[0] - 0.002, bld_bounds[2] + 0.002)
ax.set_ylim(bld_bounds[1] - 0.002, bld_bounds[3] + 0.002)
ax.set_xlabel('Longitude', fontsize=10)
ax.set_ylabel('Latitude', fontsize=10)
ax.set_title('(a) Building Height Heatmap (KDE Weighted)', fontweight='bold', fontsize=12)
ax.legend(fontsize=8)
ax.grid(True, alpha=0.1)
ax.set_aspect('equal')

# 右: 高度分布直方图
ax2 = axes[1]
valid_all = bld_wgs['levels_num'].dropna()
valid_all = valid_all[valid_all > 0]

bins = [0, 3, 6, 10, 15, 20, 30, 50, 80, 120]
labels_hist = ['1-3F', '4-6F', '7-10F', '11-15F', '16-20F', '21-30F', '31-50F', '51-80F', '81-120F']
counts, edges, patches = ax2.hist(valid_all.clip(upper=120), bins=bins, color='#e67e22',
                                    edgecolor='white', alpha=0.85, align='mid')
for i, (cnt, patch) in enumerate(zip(counts, patches)):
    if cnt > 0:
        ax2.text(patch.get_x() + patch.get_width()/2, cnt + 50,
                 f'{int(cnt):,}', ha='center', fontsize=9, fontweight='bold')

ax2.set_xlabel('Building Height (Floors)', fontsize=10)
ax2.set_ylabel('Number of Buildings', fontsize=10)
ax2.set_title('(b) Building Height Distribution', fontweight='bold', fontsize=12)
ax2.grid(axis='y', alpha=0.3)

# 标注
total_valid = len(valid_all)
med = np.median(valid_all)
ax2.axvline(med, color='red', ls='--', lw=1.5, label=f'Median={med:.0f}F')
ax2.legend(fontsize=9)

plt.suptitle('Figure 11b: Building Height (Floors) Spatial Distribution\n'
             f'Nanshan District | Valid: {total_valid:,} / {len(bld_wgs):,} buildings | Max: {valid_all.max():.0f}F',
             fontsize=11, y=0.02)

fig.tight_layout(rect=[0, 0.04, 1, 0.96])
fig.savefig(os.path.join(OUT_DIR, "p8_fig11b_building_floors_heatmap.png"),
           dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p8_fig11b_building_floors_heatmap.png")

# ================================================================
# 4. Fig11c: 高层建筑聚集与TPI剥夺叠加
# ================================================================
print("\n[4] Fig11c: 高层建筑+TPI剥夺叠加...")

fig, ax = plt.subplots(figsize=(14, 12))

# 背景: 路网
road_wgs.plot(ax=ax, color='#cccccc', linewidth=0.15, alpha=0.35)

# 底层建筑 (灰色)
lowrise = bld_wgs[bld_wgs['levels_num'].fillna(2) <= 5]
ax.scatter(lowrise.geometry.centroid.x, lowrise.geometry.centroid.y,
          c='#d3d3d3', s=2, alpha=0.4, label=f'Low-rise (<=5F, n={len(lowrise):,})')

# 中层建筑 (橙黄色)
midrise = bld_wgs[(bld_wgs['levels_num'].fillna(2) > 5) &
                    (bld_wgs['levels_num'].fillna(2) <= 20)]
ax.scatter(midrise.geometry.centroid.x, midrise.geometry.centroid.y,
          c='#f39c12', s=4, alpha=0.6, label=f'Mid-rise (6-20F, n={len(midrise):,})')

# 高层建筑 (红色)
highrise = bld_wgs[bld_wgs['levels_num'].fillna(2) > 20]
ax.scatter(highrise.geometry.centroid.x, highrise.geometry.centroid.y,
          c='#e74c3c', s=7, alpha=0.8,
          label=f'High-rise (>20F, n={len(highrise):,})')

# 叠加: 社区TPI剥夺等值线(简化版，用透明度表示)
# 加载社区可达性
gdf_comm = gpd.GeoDataFrame(
    results,
    geometry=gpd.points_from_xy(results['lng'], results['lat']),
    crs='EPSG:4326'
)

# 绘制TPI等值线
TPI_CMAP_TPI = LinearSegmentedColormap.from_list('tpi',
    ['#1a9850', '#91cf60', '#d9ef8b', '#fee08b', '#fdae61', '#f46d43', '#d73027'])
TPI_NORM_TPI = mcolors.TwoSlopeNorm(vmin=-80, vcenter=0, vmax=80)

tpi_v = gdf_comm['TPI'].values
sc = ax.scatter(gdf_comm.geometry.x, gdf_comm.geometry.y,
                c=tpi_v, cmap=TPI_CMAP_TPI, s=gdf_comm['population']/150+10,
                alpha=0.5, norm=TPI_NORM_TPI,
                edgecolors='white', linewidths=0.2,
                label=f'Community TPI (n={len(gdf_comm):,})')

# 标注最严重剥夺区域
severe = results[results['TPI'] >= 50].nlargest(3, 'TPI')
for _, row in severe.iterrows():
    ax.annotate(f"TPI={row['TPI']:.0f}%\nPop:{int(row['population']/1000):.0f}K",
                (row['lng'], row['lat']),
                fontsize=8, color='darkred', fontweight='bold',
                xytext=(8, 8), textcoords='offset points')

ax.set_xlim(bld_bounds[0] - 0.002, bld_bounds[2] + 0.002)
ax.set_ylim(bld_bounds[1] - 0.002, bld_bounds[3] + 0.002)
ax.set_xlabel('Longitude (WGS84)', fontsize=11)
ax.set_ylabel('Latitude (WGS84)', fontsize=11)
ax.set_title('(c) High-rise Building Clustering + TPI Deprivation Overlay',
             fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.12, linestyle='--')
ax.set_aspect('equal')

# 颜色条
cbar = plt.colorbar(sc, ax=ax, shrink=0.6, pad=0.02)
cbar.set_label('TPI Time Poverty Index (%)', fontsize=10)
cbar.ax.tick_params(labelsize=9)

# 图例
handles = [
    mpatches.Patch(facecolor='#d3d3d3', label=f'Low-rise <=5F ({len(lowrise):,})'),
    mpatches.Patch(facecolor='#f39c12', label=f'Mid-rise 6-20F ({len(midrise):,})'),
    mpatches.Patch(facecolor='#e74c3c', label=f'High-rise >20F ({len(highrise):,})'),
]
ax.legend(handles=handles, loc='upper left', fontsize=8,
          framealpha=0.9, title='Building Height', title_fontsize=9)

ax.text(0.02, 0.02,
        'High-rise buildings (>20F) concentrated in core districts\n'
        'may MASK time poverty of surrounding urban village residents',
        transform=ax.transAxes, fontsize=9,
        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

plt.suptitle('Figure 11c: High-rise Clustering vs. TPI Deprivation\n'
             'Nanshan District | Source: OSM Buildings + Accessibility Results',
             fontsize=11, y=0.01)

fig.tight_layout(rect=[0, 0.02, 1, 0.97])
fig.savefig(os.path.join(OUT_DIR, "p8_fig11c_highrise_tpi_overlay.png"),
           dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p8_fig11c_highrise_tpi_overlay.png")

# ================================================================
# 5. Fig11d: 建筑密度与社区可达性对比
# ================================================================
print("\n[5] Fig11d: 建筑密度与可达性对比...")

fig, axes = plt.subplots(1, 2, figsize=(18, 8))

# 左: 建筑密度网格
ax = axes[0]

# 创建100m网格统计建筑密度
import numpy as np
grid_res = 0.001  # ~100m
x_edges = np.arange(bld_bounds[0] - 0.001, bld_bounds[2] + 0.002, grid_res)
y_edges = np.arange(bld_bounds[1] - 0.001, bld_bounds[3] + 0.002, grid_res)

bld_x = bld_wgs.geometry.centroid.x.values
bld_y = bld_wgs.geometry.centroid.y.values
H, xedges, yedges = np.histogram2d(bld_x, bld_y, bins=[x_edges, y_edges])
H = np.ma.masked_where(H == 0, H)

im = ax.imshow(H.T, origin='lower',
               extent=[x_edges[0], x_edges[-1], y_edges[0], y_edges[-1]],
               cmap='Blues', alpha=0.8, aspect='equal')
cbar = plt.colorbar(im, ax=ax, shrink=0.6)
cbar.set_label('Building Count per Grid Cell (~100m x 100m)', fontsize=9)

road_wgs.plot(ax=ax, color='white', linewidth=0.1, alpha=0.3)

ax.set_xlim(bld_bounds[0], bld_bounds[2])
ax.set_ylim(bld_bounds[1], bld_bounds[3])
ax.set_xlabel('Longitude (WGS84)', fontsize=10)
ax.set_ylabel('Latitude (WGS84)', fontsize=10)
ax.set_title('(a) Building Density (100m Grid)', fontweight='bold', fontsize=12)
ax.grid(True, alpha=0.1, color='white', linewidth=0.5)

# 右: 社区可达性 + 建筑密度等值线
ax2 = axes[1]

# 背景: 建筑密度等值线
road_wgs.plot(ax=ax2, color='#cccccc', linewidth=0.1, alpha=0.3)
contours = ax2.contour(np.log1p(H.T),
                        extent=[x_edges[:-1].mean()-grid_res/2, x_edges[:-1].mean()+grid_res*(len(x_edges)-2)+grid_res/2,
                                y_edges[:-1].mean()-grid_res/2, y_edges[:-1].mean()+grid_res*(len(y_edges)-2)+grid_res/2],
                        colors='blue', linewidths=0.5, alpha=0.4, levels=5)
ax2.clabel(contours, inline=True, fontsize=7, fmt='%1.0f')

# 叠加社区可达性
acc_norm = gdf_comm['A_day_norm'].values
sc2 = ax2.scatter(gdf_comm.geometry.x, gdf_comm.geometry.y,
                  c=acc_norm, cmap='RdYlGn', s=gdf_comm['population']/200+8,
                  alpha=0.8, edgecolors='white', linewidths=0.3,
                  vmin=acc_norm.min(), vmax=acc_norm.max())
plt.colorbar(sc2, ax=ax2, shrink=0.6, label='Day Accessibility (Normalized)')

# 标注对比: 高密度+低可达性
for _, row in results.nlargest(3, 'TPI').iterrows():
    ax2.annotate(f"TPI+{row['TPI']:.0f}%",
                (row['lng'], row['lat']),
                fontsize=8, color='red', fontweight='bold',
                xytext=(5, 5), textcoords='offset points')

ax2.set_xlim(bld_bounds[0], bld_bounds[2])
ax2.set_ylim(bld_bounds[1], bld_bounds[3])
ax2.set_xlabel('Longitude (WGS84)', fontsize=10)
ax2.set_ylabel('Latitude (WGS84)', fontsize=10)
ax2.set_title('(b) Day Accessibility vs. Building Density Contours', fontweight='bold', fontsize=12)
ax2.grid(True, alpha=0.1)
ax2.set_aspect('equal')

ax2.text(0.02, 0.02,
          'Blue contours = building density\n'
          'Colors = day accessibility\n'
          'Note: High density zones ≠ high accessibility',
          transform=ax2.transAxes, fontsize=8,
          bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9),
          verticalalignment='bottom')

plt.suptitle('Figure 11d: Building Density vs. Community Accessibility\n'
             'Nanshan District | Left: 100m grid building count | Right: Day accessibility overlay',
             fontsize=11, y=0.02)

fig.tight_layout(rect=[0, 0.04, 1, 0.96])
fig.savefig(os.path.join(OUT_DIR, "p8_fig11d_building_density_accessibility.png"),
           dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print(f"  [OK] p8_fig11d_building_density_accessibility.png")

# ================================================================
# 6. 摘要统计
# ================================================================
print("\n[6] Fig11 分析摘要...")
print("=" * 60)
print("建筑AOI分析结果:")
print("=" * 60)
print(f"Total buildings: {len(bld_wgs):,}")
hr = (bld_wgs["levels_num"].fillna(2) > 20).sum()
print(f"High-rise (>20F): {hr:,} ({100*hr/len(bld_wgs):.1f}%)")
print(f"Super high-rise (>50F): {(bld_wgs["levels_num"].fillna(0) > 50).sum():,}")
bld_type_msg = "Building types: Res_low=%d / Res_mid=%d / Commercial=%d" % (
    (bld_wgs["btype_cat"] == "residential_low").sum(),
    (bld_wgs["btype_cat"] == "residential_mid").sum(),
    (bld_wgs["btype_cat"] == "commercial").sum())
print(bld_type_msg)

# TPI 与 建筑高度的关联
highrise_comm_ids = bld_wgs[bld_wgs['levels_num'].fillna(2) > 20]['nearest_community_id'].unique()
highrise_results = results[results['community_id'].isin(highrise_comm_ids)]
if len(highrise_results) > 0:
    print(f"\n高层建筑周边社区可达性:")
    print(f"  平均白天可达性: {highrise_results['A_day_norm'].mean():.4f}")
    print(f"  平均TPI: {highrise_results['TPI'].mean():.1f}%")
    print(f"  剥夺率 (TPI>0): {(highrise_results['TPI']>0).mean()*100:.1f}%")

print(f"\n生成文件:")
print(f"  p8_fig11a_building_use_type.png        建筑用途分类分布")
print(f"  p8_fig11b_building_floors_heatmap.png   建筑高度热力")
print(f"  p8_fig11c_highrise_tpi_overlay.png     高层+TPI叠加")
print(f"  p8_fig11d_building_density_accessibility.png 建筑密度+可达性")
print("=" * 60)
print("Fig11 全部图表生成完成!")
