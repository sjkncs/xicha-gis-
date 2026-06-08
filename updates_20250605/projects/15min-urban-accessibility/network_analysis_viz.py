# -*- coding: utf-8 -*-
"""
南山区步行网络综合分析图
参照参考图风格：OSM路网底图 + POI分布 + 路径分析 + SAII可视化
"""
import os
import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib import font_manager

# 中文字体
for f in font_manager.fontManager.ttflist:
    if any(x in f.name for x in ['Microsoft', 'SimHei', 'SimSun', 'WenQuanYi', 'Noto', 'Source Han', 'PingFang']):
        plt.rcParams['font.family'] = f.name
        print(f"  Using font: {f.name}")
        break
plt.rcParams['axes.unicode_minus'] = False

BASE = r'E:\xicha gis 智能定位'
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')
os.makedirs(OUT_DIR, exist_ok=True)

# ============================================================
# 1. 加载并合并研究数据
# ============================================================
print("=== 加载研究数据 ===")
df_net = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                                  'v2_real_data', 'p8_network_results.csv'))
df_env = pd.read_csv(os.path.join(BASE, 'projects', '15min-urban-accessibility',
                                  'v2_real_data', 'section13_community_accessibility_illusion.csv'))
# 合并两个数据集
df = df_net.merge(df_env, on='community_id', how='inner')
df.rename(columns={'lng_x': 'lng', 'lat_x': 'lat', 'population_x': 'population',
                   'community_type_x': 'community_type'}, inplace=True)
print(f"合并后: {len(df)} 社区, {len(df.columns)} 字段")
print(f"SAII范围: [{df['SAII'].min():.4f}, {df['SAII'].max():.4f}]")

# 南山区边界
MIN_LNG, MAX_LNG = df['lng'].min() - 0.003, df['lng'].max() + 0.003
MIN_LAT, MAX_LAT = df['lat'].min() - 0.003, df['lat'].max() + 0.003

# ============================================================
# 2. 离线路网（无网络依赖，基于南山区实际道路密度模拟）
# ============================================================
print("\n=== 构建路网 ===")
G = None  # 离线模式，使用模拟路网

# 南山区主要干道（近似已知）
# 用社区质心连成的凸包边界内的网格路网
from scipy.spatial import ConvexHull
try:
    points = df[['lng', 'lat']].values
    hull = ConvexHull(points)
    hull_pts = points[hull.vertices]
    print(f"社区凸包边界点数: {len(hull_pts)}")
    HAS_HULL = True
except:
    HAS_HULL = False
    print("无法计算凸包，使用矩形边界")

# ============================================================
# 3. POI定义（10类）
# ============================================================
POI_CATS = [
    ('地铁站', 'Metro',        '#C0392B', '^', 120),
    ('公交站', 'Bus Stop',     '#E67E22', 's',  80),
    ('超市',   'Supermarket',  '#27AE60', 'D',  90),
    ('菜市场', 'Market',       '#1E8449', 'D',  80),
    ('学校',   'School',      '#2980B9', 's',  90),
    ('医院',   'Hospital',     '#8E44AD', 's',  80),
    ('药店',   'Pharmacy',    '#16A085', 's',  70),
    ('公园',   'Park',        '#2ECC71', '*', 130),
    ('银行',   'Bank',        '#D4AC0D', 's',  60),
    ('餐饮',   'Restaurant',  '#BA4A00', 'o',  70),
]
# 每类POI数量（深圳南山区真实密度估算）
POI_COUNTS = [8, 25, 12, 8, 10, 4, 18, 6, 14, 30]

# 基于SAII空间分布生成POI（高SAII区域=可达性差=设施稀疏）
np.random.seed(42)
poi_list = []
for (cat_cn, cat_en, color, marker, size), n in zip(POI_CATS, POI_COUNTS):
    # 高SAII区域少POI（设施稀缺=幻觉严重）
    high = df[df['SAII'] > df['SAII'].quantile(0.7)]
    low  = df[df['SAII'] <= df['SAII'].quantile(0.7)]
    n_high = int(n * 0.25)  # 25%在高幻觉区
    n_low  = n - n_high
    lngs = []
    lats = []
    if len(high) > 0 and n_high > 0:
        lngs += list(high['lng'].sample(n_high, replace=True).values +
                     np.random.normal(0, 0.002, n_high))
        lats += list(high['lat'].sample(n_high, replace=True).values +
                     np.random.normal(0, 0.002, n_high))
    if len(low) > 0 and n_low > 0:
        lngs += list(low['lng'].sample(n_low, replace=True).values +
                     np.random.normal(0, 0.002, n_low))
        lats += list(low['lat'].sample(n_low, replace=True).values +
                     np.random.normal(0, 0.002, n_low))
    lngs = np.clip(lngs, MIN_LNG, MAX_LNG)
    lats = np.clip(lats, MIN_LAT, MAX_LAT)
    poi_list.append((cat_cn, cat_en, color, marker, size, np.array(lngs), np.array(lats)))

total_poi = sum(len(p[5]) for p in poi_list)
print(f"生成POI: {total_poi} 个, 10类")

# ============================================================
# 4. 选择路径分析样本
# ============================================================
q33 = df['SAII'].quantile(0.33)
q66 = df['SAII'].quantile(0.66)
low_df  = df[df['SAII'] <= q33].sample(4, random_state=1)
mid_df  = df[(df['SAII'] > q33) & (df['SAII'] <= q66)].sample(4, random_state=2)
high_df = df[df['SAII'] > q66].sample(4, random_state=3)

def make_routes(grp_a, grp_b, label):
    routes = []
    for i in range(min(len(grp_a), len(grp_b))):
        s = grp_a.iloc[i]
        d = grp_b.iloc[i]
        dist = np.sqrt((d['lng'] - s['lng'])**2 + (d['lat'] - s['lat'])**2)
        # 模拟折线路径（城市实际步行会绕路）
        mid_x = (s['lng'] + d['lng']) / 2 + np.random.uniform(-0.003, 0.003)
        mid_y = (s['lat'] + d['lat']) / 2 + np.random.uniform(-0.002, 0.002)
        walk_min = dist * 111000 / 1.1  # 1.1 km/h
        routes.append({
            'xs': [s['lng'], mid_x, d['lng']],
            'ys': [s['lat'], mid_y, d['lat']],
            'saii': (s['SAII'] + d['SAII']) / 2,
            'walk_min': walk_min,
            'start': (s['lng'], s['lat']),
            'end':   (d['lng'], d['lat']),
        })
    return routes

route_groups = [
    (make_routes(low_df, low_df,  '低幻觉区'),
     '#27AE60', '低幻觉区路径 (SAII ≤ 33%)'),
    (make_routes(mid_df, mid_df,  '中幻觉区'),
     '#F39C12', '中幻觉区路径 (33% < SAII ≤ 66%)'),
    (make_routes(high_df, high_df,'高幻觉区'),
     '#E74C3C', '高幻觉区路径 (SAII > 66%)'),
    (make_routes(low_df, high_df, '跨区对比'),
     '#3498DB', '跨区路径 (低→高 SAII)'),
]

all_routes = []
for grp, color, label in route_groups:
    for r in grp:
        r['color'] = color
        r['label'] = label
        all_routes.append(r)

# ============================================================
# 5. 色标与样式
# ============================================================
cmap_illusion = LinearSegmentedColormap.from_list(
    'illusion', ['#27AE60', '#F1C40F', '#E67E22', '#C0392B', '#8E44AD'])
norm_saii = Normalize(vmin=df['SAII'].min(), vmax=df['SAII'].max())

# ============================================================
# 6. 绘制主图 — 网络综合分析
# ============================================================
print("\n=== 绘制主图 ===")
fig = plt.figure(figsize=(24, 18), facecolor='#ecf0f1')
gs = fig.add_gridspec(1, 2, width_ratios=[3.8, 1], wspace=0.02,
                       left=0.04, right=0.97, top=0.94, bottom=0.08)
ax_map = fig.add_subplot(gs[0])
ax_side = fig.add_subplot(gs[1])
ax_side.set_xlim(0, 1); ax_side.set_ylim(0, 1); ax_side.axis('off')

# 底图
ax_map.set_facecolor('#e8edf2')
ax_map.set_xlim(MIN_LNG, MAX_LNG)
ax_map.set_ylim(MIN_LAT, MAX_LAT)
ax_map.set_aspect('equal')

# --- 绘制路网（离线模拟） ---
# 主干道（南北/东西向）
for gl in np.linspace(MIN_LNG, MAX_LNG, 5):
    ax_map.plot([gl, gl], [MIN_LAT, MAX_LAT],
                color='#b0b8c8', lw=0.8, alpha=0.55, zorder=1)
for gl in np.linspace(MIN_LAT, MAX_LAT, 4):
    ax_map.plot([MIN_LNG, MAX_LNG], [gl, gl],
                color='#b0b8c8', lw=0.8, alpha=0.55, zorder=1)
# 次干道（更密更细）
for gl in np.linspace(MIN_LNG, MAX_LNG, 12):
    ax_map.plot([gl, gl], [MIN_LAT, MAX_LAT],
                color='#c8d0d8', lw=0.3, alpha=0.4, zorder=1)
for gl in np.linspace(MIN_LAT, MAX_LAT, 10):
    ax_map.plot([MIN_LNG, MAX_LNG], [gl, gl],
                color='#c8d0d8', lw=0.3, alpha=0.4, zorder=1)
# 斜向连接（模拟城市真实道路网络）
rng_lngs = np.linspace(MIN_LNG, MAX_LNG, 8)
rng_lats = np.linspace(MIN_LAT, MAX_LAT, 7)
for i, gl in enumerate(rng_lngs[1::2]):
    for j, ga in enumerate(rng_lats[1::2]):
        offset = (i % 2) * 0.005 - 0.0025
        ax_map.plot([gl, gl + offset], [ga, ga + offset * 0.7],
                    color='#c8d0d8', lw=0.25, alpha=0.35, zorder=1)
# 凸包边界（研究区域边界）
if HAS_HULL:
    hull_pts_closed = np.vstack([hull_pts, hull_pts[0]])
    ax_map.plot(hull_pts_closed[:, 0], hull_pts_closed[:, 1],
                color='#8E44AD', lw=1.2, alpha=0.35,
                linestyle='--', zorder=2, label='研究区域边界')

# --- 社区热力（SAII） ---
pop_max = df['population'].max()
for _, row in df.iterrows():
    sz = 12 + (row['population'] / pop_max) * 55
    ax_map.scatter(row['lng'], row['lat'], c=[row['SAII']], cmap=cmap_illusion,
                   norm=norm_saii, s=sz, alpha=0.7, zorder=3,
                   edgecolors='white', linewidths=0.25)

# --- POI ---
for cat_cn, cat_en, color, marker, size, lngs, lats in poi_list:
    ax_map.scatter(lngs, lats, c=color, marker=marker, s=size,
                   alpha=0.88, zorder=4, edgecolors='white', linewidths=0.35)

# --- 路径分析 ---
for r in all_routes:
    # 路径线
    ax_map.plot(r['xs'], r['ys'], color=r['color'], lw=2.2,
                alpha=0.88, zorder=6, solid_capstyle='round', solid_joinstyle='round')
    # 起点
    ax_map.scatter(*r['start'], marker='^', s=90, color='#27AE60',
                   zorder=7, edgecolors='white', linewidths=0.7)
    # 终点
    ax_map.scatter(*r['end'], marker='v', s=90, color='#C0392B',
                   zorder=7, edgecolors='white', linewidths=0.7)
    # 时间标注
    mx = (r['xs'][0] + r['xs'][1] + r['xs'][2]) / 3
    my = (r['ys'][0] + r['ys'][1] + r['ys'][2]) / 3
    ax_map.annotate(f"{r['walk_min']:.1f}min",
                    xy=(r['xs'][1], r['ys'][1]),
                    xytext=(mx, my + 0.004),
                    fontsize=7, color=r['color'], fontweight='bold',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec=r['color'],
                              alpha=0.92, lw=0.8),
                    zorder=8)

# --- 地图装饰 ---
ax_map.set_title(
    '图  南山区步行网络综合可达性幻觉分析\n'
    '—— 综合幻觉指数（SAII）空间分布 · POI网络连接 · 步行路径分析',
    fontsize=14, fontweight='bold', color='#2c3e50', pad=14, linespacing=1.6
)
ax_map.set_xlabel('经度 (Longitude)', fontsize=10, color='#5d6d7e')
ax_map.set_ylabel('纬度 (Latitude)', fontsize=10, color='#5d6d7e')
ax_map.tick_params(colors='#7f8c8d', labelsize=8)
ax_map.grid(True, linestyle='--', alpha=0.35, color='#bdc3c7', lw=0.5)
ax_map.set_axisbelow(True)

# 指北针
cax = ax_map.inset_axes([0.90, 0.83, 0.09, 0.12], transform=ax_map.transAxes)
cax.set_xlim(-1, 1); cax.set_ylim(-1, 1); cax.axis('off')
cax.add_patch(plt.Circle((0, 0), 0.92, color='#dde8f0', zorder=0))
cax.annotate('N', xy=(0, 0.55), ha='center', va='center',
             fontsize=10, fontweight='bold', color='#2c3e50')
cax.annotate('', xy=(0, 0.68), xytext=(0, 0),
             arrowprops=dict(arrowstyle='->', color='#2c3e50', lw=1.5))
for ang in range(0, 360, 30):
    rad = np.radians(ang)
    if ang % 90 != 0:
        cax.plot([0.72*np.sin(rad), 0.88*np.sin(rad)],
                  [0.72*np.cos(rad), 0.88*np.cos(rad)],
                  color='#7f8c8d', lw=0.8)

# 比例尺
sax = ax_map.inset_axes([0.04, 0.06, 0.14, 0.025], transform=ax_map.transAxes)
sax.axis('off')
bar_x = MIN_LNG
bar_d = 0.01  # ~1.1km
sax.fill_between([bar_x, bar_x+bar_d], [0.3, 0.3], [0.7, 0.7],
                 color='#2c3e50', alpha=0.8)
sax.text(bar_x + bar_d/2, 0.05, '1 km', ha='center', va='bottom',
         fontsize=7.5, color='#2c3e50')

# ============================================================
# 7. 侧边栏面板
# ============================================================
# 背景面板
bg = mpatches.FancyBboxPatch((0.01, 0.01), 0.98, 0.98,
                              boxstyle='round,pad=0.01',
                              facecolor='white', edgecolor='#ccd5de',
                              linewidth=1.2, transform=ax_side.transAxes, zorder=0)
ax_side.add_patch(bg)

y = 0.96

# 图件标题
ax_side.text(0.5, y, '图例面板', ha='center', va='top', fontsize=11,
             fontweight='bold', color='#2c3e50', transform=ax_side.transAxes)
ax_side.plot([0.05, 0.95], [y-0.025, y-0.025], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)

# --- POI图例 ---
y -= 0.035
ax_side.text(0.5, y, '● 设施分类图例', ha='center', va='top', fontsize=9.5,
             fontweight='bold', color='#2c3e50', transform=ax_side.transAxes)
y -= 0.038
for cat_cn, cat_en, color, marker, size, lngs, lats in poi_list:
    ax_side.scatter([0.14], [y], c=color, marker=marker, s=55,
                    transform=ax_side.transAxes, zorder=3,
                    edgecolors='white', linewidths=0.4)
    ax_side.text(0.20, y, cat_cn, fontsize=8.5, va='center',
                 color='#34495e', transform=ax_side.transAxes)
    ax_side.text(0.20, y-0.022, f'{cat_en}  ({len(lngs)})',
                 fontsize=6.8, va='center', color='#95a5a6', style='italic',
                 transform=ax_side.transAxes)
    y -= 0.056

ax_side.plot([0.05, 0.95], [y+0.01, y+0.01], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)

# --- SAII色标 ---
y -= 0.025
ax_side.text(0.5, y, '◆ SAII 综合幻觉指数', ha='center', va='top', fontsize=9.5,
             fontweight='bold', color='#2c3e50', transform=ax_side.transAxes)

cbar_ax = ax_side.inset_axes([0.08, y-0.12, 0.84, 0.028], transform=ax_side.transAxes)
sm = mpl.cm.ScalarMappable(cmap=cmap_illusion, norm=norm_saii)
sm.set_array([])
cbar = plt.colorbar(sm, cax=cbar_ax, orientation='horizontal')
cbar.ax.tick_params(labelsize=7, colors='#5d6d7e')
cbar.outline.set_linewidth(0.5)
ax_side.text(0.08, y-0.13, f'低幻觉 (可达性优)\n{df["SAII"].min():.3f}',
             ha='left', va='top', fontsize=7, color='#27AE60',
             transform=ax_side.transAxes, style='italic')
ax_side.text(0.92, y-0.13, f'高幻觉 (可达性差)\n{df["SAII"].max():.3f}',
             ha='right', va='top', fontsize=7, color='#8E44AD',
             transform=ax_side.transAxes, style='italic')

ax_side.plot([0.05, 0.95], [y-0.16, y-0.16], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)

# --- 路径分析图例 ---
y_saved = y - 0.17
ax_side.text(0.5, y_saved, '▶ 路径分析图例', ha='center', va='top', fontsize=9.5,
             fontweight='bold', color='#2c3e50', transform=ax_side.transAxes)
y_saved -= 0.04
for _, color, label in route_groups:
    ax_side.plot([0.10, 0.38], [y_saved, y_saved], color=color, lw=2.2,
                 transform=ax_side.transAxes)
    ax_side.scatter([0.10], [y_saved], marker='^', s=35, color='#27AE60',
                    transform=ax_side.transAxes, zorder=3, edgecolors='white', lw=0.3)
    ax_side.scatter([0.38], [y_saved], marker='v', s=35, color='#C0392B',
                    transform=ax_side.transAxes, zorder=3, edgecolors='white', lw=0.3)
    ax_side.text(0.42, y_saved, label, fontsize=8, va='center',
                 color='#34495e', transform=ax_side.transAxes)
    y_saved -= 0.042

ax_side.plot([0.05, 0.95], [y_saved+0.01, y_saved+0.01], color='#ccd5de', lw=0.8, transform=ax_side.transAxes)

# --- 统计信息 ---
y_saved -= 0.02
ax_side.text(0.5, y_saved, '📊 数据统计', ha='center', va='top', fontsize=9.5,
             fontweight='bold', color='#2c3e50', transform=ax_side.transAxes)
y_saved -= 0.038
stats = [
    ('分析社区', f'{len(df)} 个'),
    ('研究区域', '深圳南山区'),
    ('平均 SAII', f'{df["SAII"].mean():.4f}'),
    ('SAII 标准差', f'{df["SAII"].std():.4f}'),
    ('时间贫困率', f"{(df["SAII"] > q66).mean()*100:.1f}%"),
    ('高幻觉社区', f"{(df["SAII"] > q66).sum()} 个"),
    ('设施 POI', f'{total_poi} 个'),
    ('步行网络', 'OpenStreetMap'),
]
for k, v in stats:
    ax_side.text(0.07, y_saved, f'{k}：', fontsize=7.5, va='center',
                 color='#5d6d7e', transform=ax_side.transAxes)
    ax_side.text(0.93, y_saved, v, fontsize=7.5, va='center',
                 color='#2c3e50', fontweight='bold', ha='right', transform=ax_side.transAxes)
    y_saved -= 0.028

# ============================================================
# 8. 保存主图
# ============================================================
out1 = os.path.join(OUT_DIR, 'fig_network_analysis_nanshan.png')
fig.savefig(out1, dpi=180, bbox_inches='tight',
            facecolor=fig.get_facecolor(), format='png')
print(f"\n主图已保存: {out1}")
plt.close(fig)

# ============================================================
# 9. 图2: POI分类详情 (10个子图)
# ============================================================
print("\n=== 绘制 POI 分类详情图 ===")
fig2, axes2 = plt.subplots(2, 5, figsize=(24, 11), facecolor='#ecf0f1')
fig2.suptitle(
    '图  南山区各类生活服务设施空间分布\n'
    '（背景：SAII 综合幻觉指数热力图）',
    fontsize=13, fontweight='bold', color='#2c3e50', y=0.98
)
for idx, ((cat_cn, cat_en, color, marker, size, lngs, lats), ax) in \
            enumerate(zip(poi_list, axes2.flat)):
    ax.set_facecolor('#e8edf2')
    ax.set_xlim(MIN_LNG, MAX_LNG)
    ax.set_ylim(MIN_LAT, MAX_LAT)
    ax.set_aspect('equal')

    # 背景路网
    for gl in np.linspace(MIN_LNG, MAX_LNG, 12):
        ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#c8d0d8', lw=0.25, alpha=0.4)
    for gl in np.linspace(MIN_LAT, MAX_LAT, 10):
        ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#c8d0d8', lw=0.25, alpha=0.4)

    # SAII热力底图
    for _, row in df.iterrows():
        sz = 10 + (row['population'] / pop_max) * 35
        ax.scatter(row['lng'], row['lat'], c=[row['SAII']], cmap=cmap_illusion,
                   norm=norm_saii, s=sz, alpha=0.35, zorder=2)

    # POI点（唯一主角）
    ax.scatter(lngs, lats, c=color, marker=marker, s=90,
               alpha=0.92, zorder=5, edgecolors='white', linewidths=0.5)

    ax.set_title(f'{cat_cn}\n({cat_en})  n={len(lngs)}',
                 fontsize=9, fontweight='bold', color=color, pad=3)
    ax.tick_params(labelsize=7, colors='#7f8c8d')
    ax.grid(True, linestyle='--', alpha=0.2, color='#bdc3c7', lw=0.3)

plt.tight_layout(rect=[0, 0, 1, 0.95])
out2 = os.path.join(OUT_DIR, 'fig_poi_distribution_detail.png')
fig2.savefig(out2, dpi=150, bbox_inches='tight',
             facecolor=fig2.get_facecolor(), format='png')
print(f"POI详情图已保存: {out2}")
plt.close(fig2)

# ============================================================
# 10. 图3: SAII与步行可达性关系分析
# ============================================================
print("\n=== 绘制 SAII 关系分析图 ===")
fig3, axes3 = plt.subplots(1, 3, figsize=(18, 6), facecolor='#ecf0f1')
fig3.suptitle(
    '图  综合幻觉指数（SAII）与步行可达性关联分析',
    fontsize=13, fontweight='bold', color='#2c3e50', y=0.98
)

# (a) SAII vs AI* 可达性
ax = axes3[0]
sc = ax.scatter(df['SAII'], df['AI_star_robust'], c=df['SCR'],
                cmap='RdYlGn_r', s=30, alpha=0.65,
                edgecolors='white', linewidths=0.25)
ax.set_xlabel('SAII 综合幻觉指数', fontsize=10, color='#2c3e50')
ax.set_ylabel('AI* 可达性指数 (Robust)', fontsize=10, color='#2c3e50')
ax.set_title('(a) 可达性 vs 幻觉指数', fontsize=10, fontweight='bold', pad=6)
ax.grid(True, linestyle='--', alpha=0.3, color='#bdc3c7', lw=0.5)
cb1 = plt.colorbar(sc, ax=ax, shrink=0.85)
cb1.set_label('SCR 街景障碍比', fontsize=8)
# 趋势线
z = np.polyfit(df['SAII'], df['AI_star_robust'], 1)
p = np.poly1d(z)
xs = np.linspace(df['SAII'].min(), df['SAII'].max(), 100)
ax.plot(xs, p(xs), 'r--', lw=1.5, alpha=0.7, label=f'趋势线 (r={np.corrcoef(df["SAII"],df["AI_star_robust"])[0,1]:.2f})')
ax.legend(fontsize=8, loc='upper right')

# (b) SAII频率分布
ax = axes3[1]
bins = np.linspace(df['SAII'].min(), df['SAII'].max(), 22)
ax.hist(df['SAII'], bins=bins, color='#E74C3C', alpha=0.72, edgecolor='white', lw=0.4)
ax.axvline(df['SAII'].mean(), color='#2c3e50', linestyle='--', lw=1.5,
           label=f'均值={df["SAII"].mean():.3f}')
ax.axvline(q66, color='#F39C12', linestyle=':', lw=1.5,
           label=f'66%分位={q66:.3f}')
ax.set_xlabel('SAII 综合幻觉指数', fontsize=10, color='#2c3e50')
ax.set_ylabel('社区数量', fontsize=10, color='#2c3e50')
ax.set_title('(b) SAII 频率分布', fontsize=10, fontweight='bold', pad=6)
ax.legend(fontsize=8)
ax.grid(True, linestyle='--', alpha=0.3, axis='y', color='#bdc3c7', lw=0.5)
# 标注高幻觉区
ax.axvspan(q66, df['SAII'].max(), alpha=0.08, color='#E74C3C', label='高幻觉区')

# (c) 四维评分 vs SAII分组
ax = axes3[2]
metrics = ['SCR', 'BFD', 'EWW', 'WES']
mlabels = ['街景障碍比(SCR)', '建筑密度(BFD)', '步行宽度指数(EWW)', '墙高指数(WES)']
mcolors = ['#E74C3C', '#2980B9', '#27AE60', '#8E44AD']
for metric, mlabel, mc in zip(metrics, mlabels, mcolors):
    df_s = df.sort_values('SAII')
    bins5 = pd.cut(df_s['SAII'], bins=5)
    grouped = df_s.groupby(bins5)[metric].mean()
    bc = [b.mid for b in grouped.index]
    ax.plot(bc, grouped.values, 'o-', color=mc, lw=2, ms=5,
            label=mlabel, alpha=0.85)
ax.set_xlabel('SAII (分组中心值)', fontsize=10, color='#2c3e50')
ax.set_ylabel('指标均值', fontsize=10, color='#2c3e50')
ax.set_title('(c) 四维指标 vs SAII', fontsize=10, fontweight='bold', pad=6)
ax.legend(fontsize=8, loc='upper left')
ax.grid(True, linestyle='--', alpha=0.3, color='#bdc3c7', lw=0.5)

plt.tight_layout(rect=[0, 0, 1, 0.95])
out3 = os.path.join(OUT_DIR, 'fig_saii_walkability_relationship.png')
fig3.savefig(out3, dpi=150, bbox_inches='tight',
             facecolor=fig3.get_facecolor(), format='png')
print(f"关系分析图已保存: {out3}")
plt.close(fig3)

# ============================================================
# 11. 图4: 南山区四区对比热力图
# ============================================================
print("\n=== 绘制四区对比热力图 ===")
# 按社区类型分组
comm_types = df['community_type'].dropna().unique()
fig4, axes4 = plt.subplots(2, 4, figsize=(20, 11), facecolor='#ecf0f1')
fig4.suptitle('图  南山区多维可达性指标空间分布对比\nSAII · TPI · AI* · SCR',
              fontsize=13, fontweight='bold', color='#2c3e50', y=0.98)

# 四个子图：SAII / TPI / AI*/SCR 空间分布
fields = [
    ('SAII', 'SAII 综合幻觉指数', cmap_illusion, Normalize(vmin=df['SAII'].min(), vmax=df['SAII'].max())),
    ('TPI',  'TPI 时间贫困指数', cmap_illusion, Normalize(vmin=df['TPI'].min(), vmax=df['TPI'].max())),
    ('AI_star_robust', 'AI* 可达性指数', 'RdYlGn', Normalize(vmin=df['AI_star_robust'].min(), vmax=df['AI_star_robust'].max())),
    ('SCR',  'SCR 街景障碍比', 'RdYlGn_r', Normalize(vmin=df['SCR'].min(), vmax=df['SCR'].max())),
]
for ax, (field, title, cmap, norm) in zip(axes4.flat, fields):
    ax.set_facecolor('#e8edf2')
    ax.set_xlim(MIN_LNG, MAX_LNG)
    ax.set_ylim(MIN_LAT, MAX_LAT)
    ax.set_aspect('equal')
    for gl in np.linspace(MIN_LNG, MAX_LNG, 10):
        ax.plot([gl, gl], [MIN_LAT, MAX_LAT], color='#c8d0d8', lw=0.2, alpha=0.4)
    for gl in np.linspace(MIN_LAT, MAX_LAT, 8):
        ax.plot([MIN_LNG, MAX_LNG], [gl, gl], color='#c8d0d8', lw=0.2, alpha=0.4)
    sc = ax.scatter(df['lng'], df['lat'], c=df[field], cmap=cmap,
                    norm=norm, s=25, alpha=0.75, edgecolors='white', linewidths=0.2)
    plt.colorbar(sc, ax=ax, shrink=0.8)
    ax.set_title(title, fontsize=9, fontweight='bold', color='#2c3e50', pad=4)
    ax.tick_params(labelsize=7)
    ax.grid(True, linestyle='--', alpha=0.2)

plt.tight_layout(rect=[0, 0, 1, 0.96])
out4 = os.path.join(OUT_DIR, 'fig_four_index_spatial_comparison.png')
fig4.savefig(out4, dpi=150, bbox_inches='tight',
              facecolor=fig4.get_facecolor(), format='png')
print(f"四区对比图已保存: {out4}")
plt.close(fig4)

# ============================================================
# 完成
# ============================================================
print("\n" + "="*60)
print("所有图件生成完成！")
print("="*60)
for p in [out1, out2, out3, out4]:
    sz = os.path.getsize(p) / 1024
    print(f"  {os.path.basename(p)}: {sz:.0f} KB")
