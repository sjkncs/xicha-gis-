# -*- coding: utf-8 -*-
"""
Fig11: 建筑AOI分析 — 4张独立图
Notebook companion script. Run this cell to generate Fig11a-d.
"""
import os, sys, math, random
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
from shapely.geometry import Point
from scipy.stats import gaussian_kde

# ========== 数据加载 ==========
BDIR = os.path.join(BASE_DIR, '..', 'building_data')
building_df = None
fname_list = [
    'nanshan_buildings_official_wgs.csv',
    'nanshan_buildings_fixed.csv',
    'nanshan_buildings_corrected.csv',
    '南山区-房屋楼栋基础数据_2920004003598.csv',
    'nanshan_buildings_official.csv',
]
for fname in fname_list:
    fp = os.path.join(BDIR, fname)
    if os.path.exists(fp):
        try:
            building_df = pd.read_csv(fp, encoding='utf-8-sig')
            print('[楼栋] 已加载:', fname, '| 条数:', len(building_df))
            break
        except Exception as e:
            print('[楼栋] 读取失败:', fname, str(e))
if building_df is None:
    print('[跳过] 楼栋数据不可用，跳过 Fig11')
else:
    # ---- GCJ-02 -> WGS-84 ----
    def gcj02_to_wgs84(lng, lat):
        a, b = 6378137.0, 6356752.314245
        e_ = 1 - (b*b)/(a*a)
        z = math.sqrt(lng*lng + lat*lat)
        if z < 1e-10:
            return lng, lat
        theta = math.atan2(lat, lng)
        for _ in range(5):
            t = math.sqrt(1 - e_ * (math.sin(theta)**2))
            lng_ = math.atan2(lat/math.cos(theta)/t, 1-e_/t) / 2
            lat_ = math.atan2(lat/math.cos(theta)*(1-e_)/t/t, 1-e_) / 2
            theta = theta - 0.000005
        return lng - lng_, lat - lat_

    # 坐标纠偏
    if 'wgs_lon' not in building_df.columns or building_df['wgs_lon'].isna().all():
        lon_col = next((c for c in ['gcj_lon', 'lon', 'lng', 'longitude'] if c in building_df.columns), None)
        lat_col = next((c for c in ['gcj_lat', 'lat', 'latitude'] if c in building_df.columns), None)
        if lon_col and lat_col:
            wgs = [gcj02_to_wgs84(float(r[lon_col]), float(r[lat_col]))
                   for _, r in building_df.iterrows()]
            building_df['wgs_lon'] = [p[0] for p in wgs]
            building_df['wgs_lat'] = [p[1] for p in wgs]
            print('[楼栋] GCJ-02 -> WGS-84 纠偏完成:', building_df['wgs_lon'].notna().sum(), '条')

    # 用途分类
    USE_MAP = {1:'住宅', 2:'商业', 3:'办公', 4:'工业',
               5:'公共', 6:'混合', 7:'科教', 9:'其他', 0:'未知'}
    if 'use_type' in building_df.columns:
        building_df['use_name'] = building_df['use_type'].map(USE_MAP).fillna('未知')
    elif 'building_type' in building_df.columns:
        building_df['use_name'] = building_df['building_type'].fillna('未知')
    else:
        building_df['use_name'] = '住宅'

    # 楼层
    for col in ['floors', 'floor', 'story', '楼层数', '层数']:
        if col in building_df.columns:
            building_df['floors'] = pd.to_numeric(building_df[col], errors='coerce')
            break
    if 'floors' not in building_df.columns:
        building_df['floors'] = 10
    building_df['floors'] = building_df['floors'].fillna(10)

    # 过滤
    if 'wgs_lon' in building_df.columns:
        building_df = building_df[
            building_df['wgs_lon'].between(113.85, 114.05) &
            building_df['wgs_lat'].between(22.40, 22.60)].copy()

    # GeoDataFrame
    bld_geom = [Point(xy) for xy in zip(building_df['wgs_lon'], building_df['wgs_lat'])]
    bld_gdf = gpd.GeoDataFrame(building_df, geometry=bld_geom, crs='EPSG:4326')
    bld_proj = bld_gdf.to_crs('EPSG:3857')

    # 投影准备
    gdf_proj = acc_gdf.to_crs('EPSG:3857')
    road_proj = gpd.GeoDataFrame(edges_gdf.copy()).to_crs('EPSG:3857')
    bld_xlim = (road_proj.total_bounds[0]-200, road_proj.total_bounds[2]+200)
    bld_ylim = (road_proj.total_bounds[1]-200, road_proj.total_bounds[3]+200)

    print('[楼栋] 有效楼栋:', len(building_df))
    print('[楼栋] 用途分布:', dict(building_df['use_name'].value_counts().head(6)))
    print('[楼栋] 楼层:', building_df['floors'].min(), '-', building_df['floors'].max())

    # TPI色带
    TPI_CMAP = LinearSegmentedColormap.from_list('tpi',
        ['#1a9850','#91cf60','#d9ef8b','#fee08b','#fdae61','#f46d43','#d73027'])
    TPI_NORM = mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=350)

    # ========== Fig11a ==========
    print('\n[Fig11a] 建筑用途分类...')
    fig11a, ax = plt.subplots(figsize=(14, 12))
    UC = {'住宅':'#e74c3c', '商业':'#3498db', '办公':'#9b59b6',
          '工业':'#95a5a6', '公共':'#2ecc71', '混合':'#f39c12',
          '科教':'#1abc9c', '其他':'#7f8c8d', '未知':'#bdc3c7'}
    road_proj.plot(ax=ax, color='#cccccc', linewidth=0.1, alpha=0.4)
    for uname in building_df['use_name'].value_counts().index:
        sub = bld_proj[bld_proj['use_name'] == uname]
        if len(sub) == 0:
            continue
        ax.scatter(sub.geometry.x, sub.geometry.y, c=UC.get(uname,'#7f8c8d'),
                   s=3, alpha=0.6, label=uname + ' (' + str(len(sub)) + ')')
    ax.set_xlim(bld_xlim); ax.set_ylim(bld_ylim)
    ax.set_xlabel('Longitude (Web Mercator)', fontsize=11)
    ax.set_ylabel('Latitude (Web Mercator)', fontsize=11)
    ax.set_title('(a) Building Use Type | 南山区建筑用途分类空间分布', fontweight='bold', fontsize=14)
    ax.legend(fontsize=9, loc='upper left', ncol=2, framealpha=0.9)
    ax.grid(True, alpha=0.1)
    ax.text(0.02, 0.02, 'Buildings: ' + str(len(building_df)),
            transform=ax.transAxes, fontsize=9, style='italic',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    plt.tight_layout()
    fig11a.savefig(os.path.join(BASE_DIR, 'p8_fig11a_building_use_type.png'),
                   dpi=200, bbox_inches='tight', facecolor='white')
    plt.show()
    print('  [OK] p8_fig11a_building_use_type.png')

    # ========== Fig11b ==========
    print('\n[Fig11b] 建筑高度热力...')
    fig11b, ax = plt.subplots(figsize=(14, 12))
    fv = bld_proj['floors'].values
    sc = ax.scatter(bld_proj.geometry.x, bld_proj.geometry.y,
                   c=fv, cmap='plasma', s=5, alpha=0.7,
                   norm=mcolors.Normalize(vmin=1, vmax=float(fv.max())))
    road_proj.plot(ax=ax, color='#cccccc', linewidth=0.1, alpha=0.4)
    plt.colorbar(sc, ax=ax, shrink=0.75, label='Floors (层数)')
    st = bld_proj[bld_proj['floors'] >= 50]
    if len(st) > 0:
        for _, r in st.iterrows():
            ax.scatter(r.geometry.x, r.geometry.y, facecolors='none', edgecolors='red', s=100, linewidths=2)
        ax.text(0.02, 0.97, 'Super High-rise (>50层): ' + str(len(st)) + '  Max: ' + str(int(fv.max())),
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))
    ax.text(0.02, 0.02,
            'High-rise (>10层): ' + str((fv>10).sum()) + '  Mean: ' + str(round(float(fv.mean()), 1)),
            transform=ax.transAxes, fontsize=9, style='italic',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    ax.set_xlim(bld_xlim); ax.set_ylim(bld_ylim)
    ax.set_xlabel('Longitude (Web Mercator)', fontsize=11)
    ax.set_ylabel('Latitude (Web Mercator)', fontsize=11)
    ax.set_title('(b) Building Height (Floors) | 南山区建筑高度热力分布', fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.1)
    plt.tight_layout()
    fig11b.savefig(os.path.join(BASE_DIR, 'p8_fig11b_building_floors_heatmap.png'),
                   dpi=200, bbox_inches='tight', facecolor='white')
    plt.show()
    print('  [OK] p8_fig11b_building_floors_heatmap.png')

    # ========== Fig11c ==========
    print('\n[Fig11c] 高层+TPI剥夺叠加...')
    fig11c, ax = plt.subplots(figsize=(14, 12))
    tv = gdf_proj['TPI'].values
    pv = acc_gdf['population'].values
    ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
              c=tv, cmap=TPI_CMAP, s=pv/200+15,
              alpha=0.7, edgecolors='none', norm=TPI_NORM)
    hr = bld_proj[bld_proj['floors'] > 20]
    ax.scatter(hr.geometry.x, hr.geometry.y,
               facecolors='none', edgecolors='#2c3e50', s=8, alpha=0.4,
               linewidths=0.5, label='High-rise (>20层): ' + str(len(hr)))
    sv = gdf_proj[gdf_proj['TPI'] > 50]
    if len(sv) > 0:
        ax.scatter(sv.geometry.x, sv.geometry.y,
                   facecolors='none', edgecolors='red', s=300, linewidths=2.5,
                   label='Severe Depriv (TPI>50%): ' + str(len(sv)))
    road_proj.plot(ax=ax, color='#cccccc', linewidth=0.1, alpha=0.3)
    plt.colorbar(ax.scatter(gdf_proj.geometry.x[:1], gdf_proj.geometry.y[:1],
                            c=[0], cmap=TPI_CMAP, norm=TPI_NORM).collections[0],
                  ax=ax, shrink=0.75, label='TPI (%)')
    ax.legend(fontsize=9, loc='upper left', framealpha=0.9)
    ax.set_xlim(bld_xlim); ax.set_ylim(bld_ylim)
    ax.set_xlabel('Longitude (Web Mercator)', fontsize=11)
    ax.set_ylabel('Latitude (Web Mercator)', fontsize=11)
    ax.set_title('(c) High-rise + TPI Deprivation | 高层建筑与时间贫困指数叠加', fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.1)
    ax.text(0.02, 0.02, 'Note: High-rise conc. != Good accessibility',
            transform=ax.transAxes, fontsize=9, style='italic',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    plt.tight_layout()
    fig11c.savefig(os.path.join(BASE_DIR, 'p8_fig11c_highrise_tpi_overlay.png'),
                   dpi=200, bbox_inches='tight', facecolor='white')
    plt.show()
    print('  [OK] p8_fig11c_highrise_tpi_overlay.png')

    # ========== Fig11d ==========
    print('\n[Fig11d] 建筑密度与可达性对比...')
    fig11d, axes_d = plt.subplots(1, 2, figsize=(18, 10))

    # d1: 建筑密度
    ax = axes_d[0]
    bld_pts = np.array(list(zip(bld_proj.geometry.x, bld_proj.geometry.y)))
    if len(bld_pts) > 100:
        try:
            idx = np.random.choice(len(bld_pts), min(3000, len(bld_pts)), replace=False)
            xy = bld_pts[idx]
            z = gaussian_kde(xy.T)(xy.T)
            sc0 = ax.scatter(xy[:, 0], xy[:, 1], c=z, cmap='hot_r', s=10, alpha=0.6)
            plt.colorbar(sc0, ax=ax, shrink=0.7, label='Building Density')
        except Exception:
            ax.scatter(bld_proj.geometry.x, bld_proj.geometry.y, c='#e74c3c', s=3, alpha=0.3)
    road_proj.plot(ax=ax, color='#cccccc', linewidth=0.1, alpha=0.4)
    ax.set_xlim(bld_xlim); ax.set_ylim(bld_ylim)
    ax.set_title('(d1) Building Density (KDE) | 建筑密度', fontweight='bold', fontsize=13)
    ax.set_xlabel('Web Mercator X', fontsize=10)
    ax.set_ylabel('Web Mercator Y', fontsize=10)
    ax.grid(True, alpha=0.1)

    # d2: SAI
    ax2 = axes_d[1]
    sai_v = gdf_proj['SAI'].values
    pv2 = acc_gdf['population'].values
    sc2 = ax2.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                     c=sai_v, cmap='YlGn', s=pv2/200+15,
                     alpha=0.8, edgecolors='white', linewidths=0.3,
                     norm=mcolors.Normalize(vmin=float(sai_v.min()), vmax=float(sai_v.max())))
    road_proj.plot(ax=ax2, color='#cccccc', linewidth=0.1, alpha=0.4)
    plt.colorbar(sc2, ax=ax2, shrink=0.7, label='SAI (Accessibility Index)')
    ax2.set_xlim(bld_xlim); ax2.set_ylim(bld_ylim)
    ax2.set_title('(d2) Community SAI | 社区可达性', fontweight='bold', fontsize=13)
    ax2.set_xlabel('Web Mercator X', fontsize=10)
    ax2.set_ylabel('Web Mercator Y', fontsize=10)
    ax2.grid(True, alpha=0.1)

    plt.suptitle('(d) Building Density vs SAI | 建筑密度与可达性对比  (楼栋='
                 + str(len(building_df)) + ' 社区=' + str(len(acc_gdf)) + ')',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    fig11d.savefig(os.path.join(BASE_DIR, 'p8_fig11d_building_density_accessibility.png'),
                   dpi=200, bbox_inches='tight', facecolor='white')
    plt.show()
    print('  [OK] p8_fig11d_building_density_accessibility.png')

    print('\n[Fig11] 建筑AOI分析完成 (4张独立图)')
    print('  Fig11a: p8_fig11a_building_use_type.png')
    print('  Fig11b: p8_fig11b_building_floors_heatmap.png')
    print('  Fig11c: p8_fig11c_highrise_tpi_overlay.png')
    print('  Fig11d: p8_fig11d_building_density_accessibility.png')
else:
    print('[跳过] Fig11 楼栋数据不可用')

print('\n' + '='*60)
print('Fig11 建筑AOI分析完成')
print('='*60)
