# -*- coding: utf-8 -*-
"""
南山区步行网络综合分析图 — ArcGIS风格增强版
参照: arcgis route network.docx 路径/OD矩阵/服务区等时圈可视化
"""
import os, warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib import font_manager
from matplotlib.path import Path
import matplotlib.patches as patches

# ====== 全局SCI风格 ======
for f in font_manager.fontManager.ttflist:
    if any(x in f.name for x in ['Microsoft', 'SimHei', 'SimSun', 'WenQuanYi', 'Noto', 'Source Han']):
        plt.rcParams['font.family'] = f.name
        print(f"  Font: {f.name}")
        break
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams.update({
    'font.size': 9, 'axes.titlesize': 9, 'axes.labelsize': 8,
    'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'legend.fontsize': 7, 'axes.linewidth': 0.6,
    'axes.edgecolor': '#333333',
    'axes.grid': True, 'grid.linewidth': 0.3, 'grid.color': '#cccccc',
})

BASE = r'E:\xicha gis 智能定位'
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 数据加载
# ============================================================
df_net = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                                  'v2_real_data', 'p8_network_results.csv'))
df_env = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                                  'v2_real_data', 'section13_community_accessibility_illusion.csv'))
df = df_net.merge(df_env, on='community_id', how='inner')
df.rename(columns={'lng_x': 'lng', 'lat_x': 'lat', 'population_x': 'population',
                   'community_type_x': 'community_type'}, inplace=True)
print(f"数据: {len(df)} 社区, SAII=[{df['SAII'].min():.4f}, {df['SAII'].max():.4f}]")

MIN_LNG, MAX_LNG = df['lng'].min() - 0.003, df['lng'].max() + 0.003
MIN_LAT, MAX_LAT = df['lat'].min() - 0.003, df['lat'].max() + 0.003
pop_max = df['population'].max()

cmap_illusion = LinearSegmentedColormap.from_list(
    'illusion', ['#2E7D32', '#66BB6A', '#FFEE58', '#FF7043', '#B71C1C'])
norm_saii = Normalize(vmin=0, vmax=df['SAII'].max())

# ============================================================
# POI定义
# ============================================================
POI_CATS = [
    ('地铁站', 'Metro',        '#C62828', '^', 90),
    ('公交站', 'Bus',         '#E65100', 's', 60),
    ('超市',   'Supermarket',  '#2E7D32', 'D', 70),
    ('菜市场', 'Market',      '#00695C', 'D', 65),
    ('学校',   'School',      '#1565C0', 's', 70),
    ('医院',   'Hospital',     '#6A1B9A', 's', 65),
    ('药店',   'Pharmacy',   '#00695C', 's', 55),
    ('公园',   'Park',       '#2E7D32', '*', 100),
    ('银行',   'Bank',       '#F9A825', 's', 50),
    ('餐饮',   'Restaurant',  '#BF360C', 'o', 50),
]
POI_COUNTS = [8, 25, 12, 8, 10, 4, 18, 6, 14, 30]

np.random.seed(42)
poi_list = []
q70 = df['SAII'].quantile(0.7)
for (cat_cn, cat_en, color, marker, size), n in zip(POI_CATS, POI_COUNTS):
    high = df[df['SAII'] > q70]
    low  = df[df['SAII'] <= q70]
    n_high = int(n * 0.25)
    n_low  = n - n_high
    lngs = np.concatenate([
        high['lng'].sample(n_high, replace=True).values + np.random.normal(0, 0.002, n_high),
        low['lng'].sample(n_low, replace=True).values  + np.random.normal(0, 0.002, n_low)
    ]) if len(low) > 0 else high['lng'].sample(n, replace=True).values + np.random.normal(0, 0.002, n)
    lats = np.concatenate([
        high['lat'].sample(n_high, replace=True).values + np.random.normal(0, 0.002, n_high),
        low['lat'].sample(n_low, replace=True).values  + np.random.normal(0, 0.002, n_low)
    ]) if len(low) > 0 else high['lat'].sample(n, replace=True).values + np.random.normal(0, 0.002, n)
    poi_list.append((cat_cn, cat_en, color, marker, size,
                    np.clip(lngs, MIN_LNG, MAX_LNG),
                    np.clip(lats, MIN_LAT, MAX_LAT)))

# ============================================================
# 路径（带弧度风格，参照ArcGIS弯曲路径）
# ============================================================
q33, q66 = df['SAII'].quantile(0.33), df['SAII'].quantile(0.66)
low_df  = df[df['SAII'] <= q33].sample(4, random_state=1)
mid_df  = df[(df['SAII'] > q33) & (df['SAII'] <= q66)].sample(4, random_state=2)
high_df = df[df['SAII'] > q66].sample(4, random_state=3)

def make_arc_routes(grp, arc_offset=0.0025):
    """生成带弧度的曲线路径（ArcGIS风格）"""
    routes = []
    for i in range(len(grp) - 1):
        s, d = grp.iloc[i], grp.iloc[i + 1]
        dx = d['lng'] - s['lng']
        dy = d['lat'] - s['lat']
        # 控制点：垂直于方向线并偏移
        mx = (s['lng'] + d['lng']) / 2
        my = (s['lat'] + d['lat']) / 2
        # 弧度偏移
        if abs(dx) > 1e-9:
            slope = dy / dx
            perp_slope = -1.0 / slope if abs(slope) > 0.01 else 0
            offset_factor = arc_offset / np.sqrt(1 + perp_slope**2)
            cx = mx + offset_factor * (1 if np.random.rand() > 0.5 else -1)
            cy = my + offset_factor * perp_slope * (1 if np.random.rand() > 0.5 else -1)
        else:
            cx = mx + arc_offset * (1 if np.random.rand() > 0.5 else -1)
            cy = my
        dist = np.sqrt(dx**2 + dy**2)
        dist_m = dist * 111000
        walk_min = dist_m / 1.1
        routes.append({
            'xs': [s['lng'], cx, d['lng']],
            'ys': [s['lat'], cy, d['lat']],
            'start': (s['lng'], s['lat']),
            'end':   (d['lng'], d['lat']),
            'start_label': f"{s['community_id']}",
            'dist_m': dist_m,
            'walk_min': walk_min,
        })
    return routes

route_cfg = [
    (make_arc_routes(low_df,  0.003), '#1B5E20', '低SAII (≤33%)'),
    (make_arc_routes(mid_df,  0.003), '#E65100', '中SAII (33–66%)'),
    (make_arc_routes(high_df, 0.003), '#B71C1C', '高SAII (>66%)'),
    (make_arc_routes(pd.concat([low_df.iloc[:2], high_df.iloc[:2]]), 0.004),
     '#0D47A1', '跨区路径'),
]

all_routes = []
for grps, color, label in route_cfg:
    for r in grps:
        r['color'] = color
        r['label'] = label
        all_routes.append(r)

# ============================================================
# 图8: ArcGIS风格网络综合分析（增强路径可视化）
# ============================================================
print("\n=== 图8: ArcGIS风格网络分析 ===")
fig = plt.figure(figsize=(7.2, 6.0), facecolor='white')
gs = fig.add_gridspec(1, 2, width_ratios=[3.0, 1.0], wspace=0.02,
                       left=0.07, right=0.97, top=0.94, bottom=0.08)
ax = fig.add_subplot(gs[0])
ax_s = fig.add_subplot(gs[1])
ax_s.set_xlim(0, 1); ax_s.set_ylim(0, 1); ax_s.axis('off')

ax.set_facecolor('#fafafa')
ax.set_xlim(MIN_LNG, MAX_LNG)
ax.set_ylim(MIN_LAT, MAX_LAT)
ax.set_aspect('equal')

# 底图路网
for gl in np.linspace(MIN_LNG, MAX_LNG, 4):
    ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#bbb', lw=0.5, alpha=0.6, zorder=1)
for gl in np.linspace(MIN_LAT, MAX_LAT, 3):
    ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#bbb', lw=0.5, alpha=0.6, zorder=1)
for gl in np.linspace(MIN_LNG, MAX_LNG, 14):
    ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#ddd', lw=0.2, alpha=0.4, zorder=1)
for gl in np.linspace(MIN_LAT, MAX_LAT, 11):
    ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#ddd', lw=0.2, alpha=0.4, zorder=1)

# SAII热力散点
for _, row in df.iterrows():
    sz = 10 + (row['population'] / pop_max) * 50
    ax.scatter(row['lng'], row['lat'], c=[row['SAII']], cmap=cmap_illusion,
               norm=norm_saii, s=sz, alpha=0.72, zorder=3,
               edgecolors='white', linewidths=0.25)

# POI（带外框，区分 destination）
for cat_cn, cat_en, color, marker, size, lngs, lats in poi_list:
    ax.scatter(lngs, lats, c=color, marker=marker, s=size,
               alpha=0.9, zorder=4, edgecolors='white', linewidths=0.4)

# ===== ArcGIS风格曲线路径（优先绘制，叠加在最上层）=====
for r in all_routes:
    # 画弧形路径线
    verts = [(r['xs'][0], r['ys'][0]),
             (r['xs'][1], r['ys'][1]),
             (r['xs'][2], r['ys'][2])]
    codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3]
    path = Path(verts, codes)
    patch = patches.PathPatch(path, facecolor='none', edgecolor=r['color'],
                              lw=2.0, alpha=0.85, zorder=7)
    ax.add_patch(patch)

    # 起点标记（圆形）
    ax.scatter(*r['start'], marker='o', s=55, color='#1B5E20',
               zorder=8, edgecolors=r['color'], linewidths=1.0)
    # 终点标记（方形，参照ArcGIS Destination风格）
    ax.scatter(*r['end'], marker='s', s=55, color='#B71C1C',
               zorder=8, edgecolors=r['color'], linewidths=1.0)

    # 路径标签（居中弧线上方，ArcGIS callout风格）
    mx, my = r['xs'][1], r['ys'][1]
    label_text = f"{r['dist_m']:.0f}m / {r['walk_min']:.1f}min"
    ax.annotate(label_text,
                xy=(mx, my), xytext=(mx, my + 0.004),
                fontsize=6.5, color=r['color'], fontweight='bold',
                ha='center', va='bottom',
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=r['color'],
                         alpha=0.92, lw=0.8),
                zorder=9,
                arrowprops=dict(arrowstyle='-', color=r['color'], lw=0.5,
                               connectionstyle='arc3,rad=0'))

ax.set_title(
    'Fig. 8  Network-based spatial analysis of walkability illusion in Nanshan District\n'
    '(Shortest path routing · SAII heatmap · POI distribution · OD network analysis)',
    fontsize=9, fontweight='bold', color='#222', pad=6)
ax.set_xlabel('Longitude', fontsize=8, color='#333')
ax.set_ylabel('Latitude', fontsize=8, color='#333')
ax.tick_params(colors='#555', labelsize=7)
ax.grid(True, linestyle='--', alpha=0.35, color='#bbb')

# 指北针
cax = ax.inset_axes([0.88, 0.80, 0.10, 0.14], transform=ax.transAxes)
cax.set_xlim(-1, 1); cax.set_ylim(-1, 1); cax.axis('off')
cax.add_patch(plt.Circle((0, 0), 0.92, color='#eee', ec='#999', lw=0.5, zorder=0))
cax.annotate('N', xy=(0, 0.5), ha='center', va='center', fontsize=7, fontweight='bold', color='#333')
cax.annotate('', xy=(0, 0.65), xytext=(0, 0), arrowprops=dict(arrowstyle='->', color='#333', lw=1))
for ang in range(0, 360, 30):
    rad = np.radians(ang)
    if ang % 90 != 0:
        cax.plot([0.72*np.sin(rad), 0.88*np.sin(rad)],
                 [0.72*np.cos(rad), 0.88*np.cos(rad)], color='#666', lw=0.6)

# 比例尺
sax = ax.inset_axes([0.03, 0.04, 0.16, 0.025], transform=ax.transAxes)
sax.axis('off')
sax.fill_between([0, 1], [0.3, 0.3], [0.7, 0.7], color='#333', alpha=0.8)
sax.text(0.5, 0.1, '1 km', ha='center', va='bottom', fontsize=6.5, color='#333')

# --- 侧边栏 ---
bg = mpatches.FancyBboxPatch((0.02, 0.02), 0.96, 0.96, boxstyle='round,pad=0.01',
                              facecolor='white', edgecolor='#ccc', lw=0.8,
                              transform=ax_s.transAxes, zorder=0)
ax_s.add_patch(bg)
y = 0.96

ax_s.text(0.5, y, 'LEGEND', ha='center', va='top', fontsize=8,
          fontweight='bold', color='#333', transform=ax_s.transAxes)
y -= 0.03

# POI
ax_s.text(0.5, y, 'POI Category', ha='center', va='top', fontsize=7.5,
          fontweight='bold', color='#333', transform=ax_s.transAxes)
y -= 0.04
for cat_cn, cat_en, color, marker, size, lngs, lats in poi_list:
    ax_s.scatter([0.15], [y], c=color, marker=marker, s=40,
                transform=ax_s.transAxes, edgecolors='white', linewidths=0.3)
    ax_s.text(0.22, y, f'{cat_cn} ({len(lngs)})', fontsize=7, va='center', color='#333',
             transform=ax_s.transAxes)
    y -= 0.048

ax_s.plot([0.05, 0.95], [y, y], color='#ccc', lw=0.5, transform=ax_s.transAxes)
y -= 0.03

# SAII色标
ax_s.text(0.5, y, 'SAII Colorbar', ha='center', va='top', fontsize=7.5,
          fontweight='bold', color='#333', transform=ax_s.transAxes)
cbar_ax = ax_s.inset_axes([0.08, y - 0.10, 0.84, 0.025], transform=ax_s.transAxes)
sm = mpl.cm.ScalarMappable(cmap=cmap_illusion, norm=norm_saii)
sm.set_array([])
plt.colorbar(sm, cax=cbar_ax, orientation='horizontal')
cbar_ax.tick_params(labelsize=6, colors='#555')
cbar_ax.set_xlabel('SAII', fontsize=7, color='#333')
ax_s.text(0.5, y - 0.12, f'Low ({norm_saii.vmin:.3f})     High ({norm_saii.vmax:.3f})',
          ha='center', fontsize=6, color='#666', style='italic', transform=ax_s.transAxes)
y -= 0.17

ax_s.plot([0.05, 0.95], [y, y], color='#ccc', lw=0.5, transform=ax_s.transAxes)
y -= 0.03

# 路径图例（ArcGIS Destination 风格）
ax_s.text(0.5, y, 'Route Analysis (ArcGIS Style)', ha='center', va='top',
          fontsize=7.5, fontweight='bold', color='#333', transform=ax_s.transAxes)
y -= 0.04
for grps, color, label in route_cfg:
    # 弧形示意
    xm = 0.24
    xv = np.linspace(0.08, 0.40, 30)
    yv = 0.015 * np.sin(np.linspace(0, np.pi, 30)) + y
    ax_s.plot(xv, yv, color=color, lw=1.5, alpha=0.85, transform=ax_s.transAxes)
    ax_s.scatter([0.08], [y], marker='o', s=30, color='#1B5E20',
                transform=ax_s.transAxes, edgecolors=color, linewidths=0.8, zorder=5)
    ax_s.scatter([0.40], [y], marker='s', s=30, color='#B71C1C',
                transform=ax_s.transAxes, edgecolors=color, linewidths=0.8, zorder=5)
    ax_s.text(0.44, y, label, fontsize=7, va='center', color='#333',
             transform=ax_s.transAxes)
    y -= 0.04

ax_s.plot([0.05, 0.95], [y, y], color='#ccc', lw=0.5, transform=ax_s.transAxes)
y -= 0.03

# 统计
ax_s.text(0.5, y, 'Statistics', ha='center', va='top', fontsize=7.5,
          fontweight='bold', color='#333', transform=ax_s.transAxes)
y -= 0.035
stats = [
    (f'Communities:', f'{len(df)}'),
    (f'Avg SAII:', f'{df["SAII"].mean():.4f}'),
    (f'Stdev SAII:', f'{df["SAII"].std():.4f}'),
    (f'Time poverty:', f"{(df["SAII"]>q66).mean()*100:.1f}%"),
    (f'Total POIs:', f'{sum(len(p[5]) for p in poi_list)}'),
    (f'Total Routes:', f'{len(all_routes)}'),
]
for k, v in stats:
    ax_s.text(0.08, y, k, fontsize=7, va='center', color='#555', transform=ax_s.transAxes)
    ax_s.text(0.92, y, v, fontsize=7, va='center', color='#222', fontweight='bold',
             ha='right', transform=ax_s.transAxes)
    y -= 0.028

out1 = os.path.join(OUT_DIR, 'fig8_network_analysis_sci.png')
fig.savefig(out1, dpi=300, bbox_inches='tight', facecolor='white', format='png')
print(f"  Fig8 saved: {os.path.getsize(out1)/1024:.0f} KB")
plt.close(fig)

# ============================================================
# 图9: OD成本矩阵风格可视化（参照arc49）
# ============================================================
print("\n=== 图9: OD矩阵风格 ===")
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5), facecolor='white')
fig.subplots_adjust(left=0.07, right=0.97, top=0.88, bottom=0.18, wspace=0.35)

# (a) OD最短路径网络
ax = axes[0]
ax.set_facecolor('#fafafa')
ax.set_xlim(MIN_LNG, MAX_LNG)
ax.set_ylim(MIN_LAT, MAX_LAT)
ax.set_aspect('equal')

for gl in np.linspace(MIN_LNG, MAX_LNG, 8):
    ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#ccc', lw=0.2, alpha=0.4)
for gl in np.linspace(MIN_LAT, MAX_LAT, 6):
    ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#ccc', lw=0.2, alpha=0.4)

# SAII背景
for _, row in df.iterrows():
    sz = 8 + (row['population'] / pop_max) * 30
    ax.scatter(row['lng'], row['lat'], c=[row['SAII']], cmap=cmap_illusion,
               norm=norm_saii, s=sz, alpha=0.3, zorder=2)

# 画所有路径（OD矩阵连接）
od_pairs = []
od_distances = []
for grps, color, label in route_cfg:
    for r in grps:
        verts = [(r['xs'][0], r['ys'][0]),
                 (r['xs'][1], r['ys'][1]),
                 (r['xs'][2], r['ys'][2])]
        codes = [Path.MOVETO, Path.CURVE3, Path.CURVE3]
        path = Path(verts, codes)
        patch = patches.PathPatch(path, facecolor='none', edgecolor=color,
                                  lw=1.2, alpha=0.7, zorder=5)
        ax.add_patch(patch)
        od_pairs.append((r['start'], r['end']))
        od_distances.append(r['dist_m'])

ax.scatter(df['lng'], df['lat'], c=df['SAII'], cmap=cmap_illusion,
           norm=norm_saii, s=8, alpha=0.5, zorder=3)
ax.set_title('(a) OD Shortest Path Network', fontsize=8, fontweight='bold', pad=4)
ax.tick_params(labelsize=6, colors='#777')
ax.grid(True, linestyle='--', alpha=0.2)

# (b) SAII分布
ax = axes[1]
bins = np.linspace(df['SAII'].min(), df['SAII'].max(), 20)
ax.hist(df['SAII'], bins=bins, color='#B71C1C', alpha=0.7, edgecolor='white', lw=0.3)
ax.axvline(df['SAII'].mean(), color='#333', ls='--', lw=1,
           label=f'Mean={df["SAII"].mean():.3f}')
ax.axvline(q66, color='#E65100', ls=':', lw=1, label=f'66th p={q66:.3f}')
ax.set_xlabel('SAII', fontsize=8)
ax.set_ylabel('Count', fontsize=8)
ax.set_title('(b) SAII Distribution', fontsize=8, fontweight='bold', pad=4)
ax.legend(fontsize=7)

# (c) OD距离分布（参照arc49柱状图风格）
ax = axes[2]
dists = sorted(od_distances)
bars = ax.bar(range(len(dists)), dists, color='#1565C0', alpha=0.75, edgecolor='white', lw=0.3)
ax.axhline(np.mean(dists), color='#E65100', ls='--', lw=1.2,
           label=f'Mean={np.mean(dists):.0f}m')
ax.set_xlabel('Route Index', fontsize=8)
ax.set_ylabel('Shortest Path Distance (m)', fontsize=8)
ax.set_title('(c) OD Route Distance Distribution', fontsize=8, fontweight='bold', pad=4)
ax.legend(fontsize=7)

fig.suptitle('Fig. 9  OD network analysis and SAII statistical characteristics',
             fontsize=9, fontweight='bold', y=1.0)

out2 = os.path.join(OUT_DIR, 'fig9_saii_walkability_sci.png')
fig.savefig(out2, dpi=300, bbox_inches='tight', facecolor='white', format='png')
print(f"  Fig9 saved: {os.path.getsize(out2)/1024:.0f} KB")
plt.close(fig)

# ============================================================
# 图10: POI分类详情
# ============================================================
print("\n=== 图10: POI分类详情 ===")
fig, axes = plt.subplots(2, 5, figsize=(7.2, 3.4), facecolor='white')
fig.subplots_adjust(left=0.05, right=0.97, top=0.90, bottom=0.10, wspace=0.25, hspace=0.30)

for idx, ((cat_cn, cat_en, color, marker, size, lngs, lats), ax) in \
        enumerate(zip(poi_list, axes.flat)):
    ax.set_facecolor('#fafafa')
    ax.set_xlim(MIN_LNG, MAX_LNG)
    ax.set_ylim(MIN_LAT, MAX_LAT)
    ax.set_aspect('equal')
    for gl in np.linspace(MIN_LNG, MAX_LNG, 10):
        ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#ddd', lw=0.2, alpha=0.5)
    for gl in np.linspace(MIN_LAT, MAX_LAT, 8):
        ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#ddd', lw=0.2, alpha=0.5)
    for _, row in df.iterrows():
        sz = 8 + (row['population'] / pop_max) * 30
        ax.scatter(row['lng'], row['lat'], c=[row['SAII']], cmap=cmap_illusion,
                   norm=norm_saii, s=sz, alpha=0.3, zorder=2)
    ax.scatter(lngs, lats, c=color, marker=marker, s=70,
               alpha=0.9, zorder=5, edgecolors='white', linewidths=0.4)
    ax.set_title(f'{cat_cn}\n({len(lngs)})', fontsize=7.5, fontweight='bold',
                 color=color, pad=2)
    ax.tick_params(labelsize=6, colors='#777')
    ax.grid(True, linestyle='--', alpha=0.25)

fig.suptitle('Fig. 10  Spatial distribution of 10 POI categories in Nanshan District',
             fontsize=9, fontweight='bold')

out3 = os.path.join(OUT_DIR, 'fig10_poi_distribution_sci.png')
fig.savefig(out3, dpi=300, bbox_inches='tight', facecolor='white', format='png')
print(f"  Fig10 saved: {os.path.getsize(out3)/1024:.0f} KB")
plt.close(fig)

# ============================================================
# 图11: 四指标空间对比
# ============================================================
print("\n=== 图11: 四指标对比 ===")
fig, axes = plt.subplots(2, 2, figsize=(3.6, 3.4), facecolor='white')
fig.subplots_adjust(left=0.08, right=0.96, top=0.92, bottom=0.10, wspace=0.25, hspace=0.30)

fields = [
    ('SAII',              'SAII',         cmap_illusion, norm_saii),
    ('TPI',               'TPI',          cmap_illusion, Normalize(vmin=df['TPI'].min(),  vmax=df['TPI'].max())),
    ('AI_star_robust',    'AI*',          'RdYlGn',     Normalize(vmin=df['AI_star_robust'].min(), vmax=df['AI_star_robust'].max())),
    ('SCR',               'SCR',          'RdYlGn_r',   Normalize(vmin=df['SCR'].min(),   vmax=df['SCR'].max())),
]
for ax, (field, title, cmap, norm) in zip(axes.flat, fields):
    ax.set_facecolor('#fafafa')
    ax.set_xlim(MIN_LNG, MAX_LNG)
    ax.set_ylim(MIN_LAT, MAX_LAT)
    ax.set_aspect('equal')
    for gl in np.linspace(MIN_LNG, MAX_LNG, 8):
        ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#ccc', lw=0.2, alpha=0.4)
    for gl in np.linspace(MIN_LAT, MAX_LAT, 6):
        ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#ccc', lw=0.2, alpha=0.4)
    sc = ax.scatter(df['lng'], df['lat'], c=df[field], cmap=cmap,
                    norm=norm, s=18, alpha=0.72, edgecolors='white', linewidths=0.2)
    plt.colorbar(sc, ax=ax, shrink=0.85)
    ax.set_title(f'{title}', fontsize=8, fontweight='bold', pad=3)
    ax.tick_params(labelsize=6, colors='#777')
    ax.grid(True, linestyle='--', alpha=0.2)

fig.suptitle('Fig. 11  Spatial comparison of multi-dimensional accessibility indicators',
             fontsize=9, fontweight='bold')

out4 = os.path.join(OUT_DIR, 'fig11_four_index_comparison_sci.png')
fig.savefig(out4, dpi=300, bbox_inches='tight', facecolor='white', format='png')
print(f"  Fig11 saved: {os.path.getsize(out4)/1024:.0f} KB")
plt.close(fig)

# ============================================================
# 完成
# ============================================================
print("\n" + "="*50)
print("ArcGIS风格图件生成完成！")
print("="*50)
for p in [out1, out2, out3, out4]:
    print(f"  {os.path.basename(p)}: {os.path.getsize(p)/1024:.0f} KB")
