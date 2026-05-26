# -*- coding: utf-8 -*-
"""
预处理器: 从 graphml 生成道路 shapefile 并运行研究级可视化
"""
import os, sys, io
import warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString, Point
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OSM  = os.path.join(BASE, 'osm_data')

FONT_CJK = ['Source Han Sans SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
            'Microsoft YaHei', 'SimHei', 'PingFang SC', 'STHeiti']
plt.rcParams['font.family'] = FONT_CJK + ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['legend.title_fontsize'] = 10
plt.rcParams['figure.titlesize'] = 14

NS_POP = 1844400
NS_POP_SOURCE = "Nanshan District Government (szns.gov.cn)"
NS_YEAR = 2025

print("=" * 70)
print("Step 1: Load graphml and generate road shapefile")
print("=" * 70)

graphml_path = os.path.join(OSM, "road_versions", "road_network.graphml")
G = nx.read_graphml(graphml_path)
print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, type={type(G)}")

first_node = list(G.nodes())[0]
print(f"Node attrs: {list(G.nodes[first_node].keys())}")
first_edge = list(G.edges(keys=True))[0]
u, v, key = first_edge
edge_data = G.edges[u, v, key]
print(f"Edge attrs: {list(edge_data.keys())}")
print(f"Has geometry: {'geometry' in edge_data}")

edges_list = []
missing_geom = 0
debug_count = 0
for u, v, key, data in G.edges(data=True, keys=True):
    geom = None
    if 'geometry' in data and data['geometry'] is not None:
        geom = data['geometry']
    elif 'wkt' in data:
        try:
            from shapely import wkt as shapely_wkt
            geom = shapely_wkt.loads(data['wkt'])
        except Exception as e:
            pass
    else:
        try:
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            x1 = u_data.get('x')
            y1 = u_data.get('y')
            x2 = v_data.get('x')
            y2 = v_data.get('y')
            if x1 is not None and x2 is not None and y1 is not None and y2 is not None:
                geom = LineString([(x1, y1), (x2, y2)])
            elif debug_count < 3:
                debug_count += 1
                print(f"  DEBUG: node {u[:8]} x={x1} y={y1}, node {v[:8]} x={x2} y={y2}")
        except Exception as e:
            if debug_count < 3:
                debug_count += 1
                print(f"  DEBUG EXC: {e}")
            pass
    if geom is not None:
        edges_list.append({'geometry': geom, **data})
    else:
        missing_geom += 1

road_gdf = gpd.GeoDataFrame(edges_list, crs='EPSG:4326')
print(f"Converted: {len(road_gdf)} edges ({missing_geom} skipped)")

shp_base = os.path.join(OSM, 'nanshan_road_network')
road_gdf.to_file(shp_base, driver='ESRI Shapefile')
print(f"Saved shapefile: {shp_base}.shp")

geojson_path = os.path.join(OSM, 'nanshan_road_network.geojson')
road_gdf.to_file(geojson_path, driver='GeoJSON')
print(f"Saved GeoJSON: {geojson_path}")

print("\n" + "=" * 70)
print("Step 2: Load research data")
print("=" * 70)

results = pd.read_csv(os.path.join(BASE, 'p8_network_results.csv'))
road_ns = gpd.read_file(shp_base + '.shp')
poi_df = pd.read_csv(os.path.join(OSM, 'anshan_poi_integrated_v3.csv'), low_memory=False)

print(f"Communities: {len(results)}, Total pop: {results['population'].sum():,}")
print(f"Road edges: {len(road_ns)}, POI count: {len(poi_df)}")

geometry = [Point(xy) for xy in zip(results['lng'], results['lat'])]
gdf = gpd.GeoDataFrame(results, geometry=geometry, crs='EPSG:4326')
gdf_proj = gdf.to_crs('EPSG:3857')
road_proj = road_ns.to_crs('EPSG:3857')

TPI_CMAP = LinearSegmentedColormap.from_list('tpi',
    ['#1a9850', '#91cf60', '#d9ef8b', '#fee08b', '#fdae61', '#f46d43', '#d73027'])
TPI_NORM = mcolors.TwoSlopeNorm(vmin=-100, vcenter=0, vmax=350)
total_pop = results['population'].sum()

print("\n[Fig1] Study area...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

ax = axes[0]
road_proj.plot(ax=ax, color='#cccccc', linewidth=0.25, alpha=0.5)
pop_v = gdf_proj['population'].values
sc = ax.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                c=pop_v, cmap='YlOrRd', s=pop_v/300+8, alpha=0.85,
                edgecolors='white', linewidths=0.3,
                norm=mcolors.Normalize(vmin=pop_v.min(), vmax=pop_v.max()))
plt.colorbar(sc, ax=ax, shrink=0.75, label='Population')
ax.set_xlim(road_proj.total_bounds[0]-300, road_proj.total_bounds[2]+300)
ax.set_ylim(road_proj.total_bounds[1]-300, road_proj.total_bounds[3]+300)
ax.set_xlabel('Longitude (Web Mercator)', fontsize=11)
ax.set_ylabel('Latitude (Web Mercator)', fontsize=11)
ax.set_title('(a) Road Network & Community Distribution', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.15, linestyle='--')
info = f'Nanshan District, Shenzhen\nPopulation: {total_pop/1e4:.2f}M ({NS_YEAR})\nCommunities: {len(gdf):,}'
ax.text(0.02, 0.98, info, transform=ax.transAxes, fontsize=10, va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))

ax = axes[1]
colors_type = plt.cm.Set2(np.linspace(0, 1, gdf_proj['community_type'].nunique()))
type_pop = gdf_proj.groupby('community_type')['population'].sum().sort_values(ascending=True)
wedges, texts, autotexts = ax.pie(type_pop.values, labels=None, autopct='%1.1f%%',
                                   colors=colors_type[:len(type_pop)], startangle=135,
                                   pctdistance=0.78, wedgeprops=dict(width=0.7))
for at in autotexts:
    at.set_fontsize(9)
    at.set_fontweight('bold')
ax.set_title('(b) Population by Community Type', fontweight='bold', fontsize=13)
ax.legend(wedges, type_pop.index, fontsize=9, loc='center left',
           bbox_to_anchor=(0.92, 0.5), title='Type', title_fontsize=10)
ax.text(0.02, -0.15, f'Total: {total_pop/1e4:.2f}M | Source: {NS_POP_SOURCE}',
        transform=ax.transAxes, fontsize=9, style='italic')

plt.suptitle('Figure 1: Study Area & Population Distribution\n'
             f'Data Source: {NS_POP_SOURCE} | Population: {total_pop/1e4:.2f}M ({NS_YEAR})',
             fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(BASE, 'p8_fig1_study_area.png'), dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print("  [OK] p8_fig1_study_area.png")

print("\n[Fig2] Day vs Night + TPI distribution...")
fig, axes = plt.subplots(1, 2, figsize=(16, 6))

ax = axes[0]
day_v = gdf['A_day_norm'].values
night_v = gdf['A_night_norm'].values
pop_v = gdf['population'].values

sc = ax.scatter(day_v, night_v, c=pop_v, cmap='YlOrRd', s=pop_v/200+12,
                alpha=0.8, edgecolors='white', linewidths=0.4)
ax.plot([0, 1], [0, 1], 'k--', alpha=0.3, lw=1.5)
ax.set_xlabel('Day Accessibility (Normalized 2SFCA)', fontsize=11)
ax.set_ylabel('Night Accessibility (Normalized 2SFCA)', fontsize=11)
ax.set_title('(a) Day vs Night Accessibility Scatter', fontweight='bold', fontsize=13)
ax.grid(True, alpha=0.3)
ax.fill_between([0, 1], [0, 1], [1, 1], alpha=0.08, color='red', label='Night < Day (Deprivation)')
ax.fill_between([0, 1], [0, 0], [0, 1], alpha=0.08, color='green', label='Night > Day (Advantage)')
ax.legend(fontsize=10, loc='upper left')

for _, row in gdf.nlargest(5, 'TPI').iterrows():
    ax.annotate(f"ID{int(row['community_id'])}\nTPI:{row['TPI']:.0f}%",
                (row['A_day_norm'], row['A_night_norm']),
                fontsize=8, color='darkred', fontweight='bold',
                xytext=(5, 5), textcoords='offset points')

cbar = plt.colorbar(sc, ax=ax, shrink=0.75)
cbar.set_label('Population', fontsize=10)

ax = axes[1]
tpi = gdf['TPI'].values
n_bins = 35
n, bins, patches = ax.hist(tpi, bins=n_bins, color='steelblue', alpha=0.75, edgecolor='white', lw=0.5)
for i, patch in enumerate(patches):
    bc = (bins[i]+bins[i+1])/2
    if bc < 0:
        patch.set_facecolor('#1a9850')
    elif bc < 50:
        patch.set_facecolor('#f46d43')
    else:
        patch.set_facecolor('#d73027')
ax.axvline(x=0, color='black', ls='--', lw=2, label='No gap (TPI=0)')
ax.axvline(x=tpi.mean(), color='red', ls='-', lw=2, label=f'Mean TPI: {tpi.mean():.1f}%')
ax.axvline(x=np.median(tpi), color='orange', ls='-', lw=1.8, label=f'Median TPI: {np.median(tpi):.1f}%')
ax.set_xlabel('Time Poverty Index (TPI, %)', fontsize=11)
ax.set_ylabel('Community Count', fontsize=11)
ax.set_title('(b) TPI Distribution Across Communities', fontweight='bold', fontsize=13)
ax.legend(fontsize=10, loc='upper left')
ax.grid(True, alpha=0.3, axis='y')

dep = gdf[gdf['TPI'] > 5]
dep_pop = dep['population'].sum()
ax.text(0.97, 0.95,
        f'Night-deprived: {len(dep)}/{len(gdf)}\n'
        f'  ({100*len(dep)/len(gdf):.1f}% of communities)\n'
        f'Affected pop: {dep_pop/1e4:.1f}K\n'
        f'  ({100*dep_pop/total_pop:.1f}% of total pop)',
        transform=ax.transAxes, fontsize=10, ha='right', va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9))

plt.suptitle('Figure 2: Day vs Night Accessibility Analysis', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(BASE, 'p8_fig2_day_night.png'), dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print("  [OK] p8_fig2_day_night.png")

print("\n[Fig3] Spatial distribution...")
fig, axes = plt.subplots(2, 2, figsize=(16, 14))

panels = [
    ('(a) Day Accessibility', 'A_day_norm', 'RdYlGn', None),
    ('(b) Night Accessibility', 'A_night_norm', 'RdYlGn', None),
    ('(c) Time Poverty Index (TPI)', 'TPI', TPI_CMAP, TPI_NORM),
    ('(d) Population-Weighted TPI (SAII)', 'SAII', 'YlOrRd', None),
]

for ax_p, (title, col, cmap, norm) in zip(axes.flat, panels):
    vals = gdf_proj[col].values
    if norm is None:
        norm = mcolors.Normalize(vmin=vals.min(), vmax=vals.max())
    sc = ax_p.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                    c=vals, cmap=cmap, s=gdf_proj['population']/200+15,
                    alpha=0.85, edgecolors='white', linewidths=0.3, norm=norm)
    road_proj.plot(ax=ax_p, color='#cccccc', linewidth=0.15, alpha=0.35)
    cbar = plt.colorbar(sc, ax=ax_p, shrink=0.6)
    cbar.ax.tick_params(labelsize=9)
    ax_p.set_xlim(road_proj.total_bounds[0]-200, road_proj.total_bounds[2]+200)
    ax_p.set_ylim(road_proj.total_bounds[1]-200, road_proj.total_bounds[3]+200)
    ax_p.set_title(title, fontweight='bold', fontsize=13)
    ax_p.grid(True, alpha=0.12)
    if col == 'TPI':
        severe = gdf_proj[gdf_proj['TPI'] > 50]
        ax_p.scatter(severe.geometry.x, severe.geometry.y,
                   facecolors='none', edgecolors='darkred', s=250, linewidths=2)
        for _, row in severe.iterrows():
            ax_p.annotate(f"C{int(row['community_id'])}\n{row['TPI']:.0f}%",
                        (row.geometry.x+250, row.geometry.y+250),
                        fontsize=8, color='darkred', fontweight='bold')

plt.suptitle('Figure 3: Spatial Accessibility Distribution\n'
             f'Nanshan District, Shenzhen | Population: {total_pop/1e4:.2f}M | Source: {NS_POP_SOURCE}',
             fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(BASE, 'p8_fig3_spatial.png'), dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print("  [OK] p8_fig3_spatial.png")

print("\n[Fig4] Night service + SAII Top...")
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

ax = axes[0]
type_stats = poi_df.groupby('facility_type').agg(
    total=('night_service_final', 'count'),
    night=('night_service_final', 'sum')
).reset_index()
type_stats['night_rate'] = type_stats['night'] / type_stats['total'] * 100
type_stats = type_stats.sort_values('night_rate')

y_pos = np.arange(len(type_stats))
colors_fc = ['#d73027' if r < 10 else '#f46d43' if r < 30 else '#fdae61' if r < 50 else '#1a9850'
             for r in type_stats['night_rate']]
ax.barh(y_pos, type_stats['night_rate'], color=colors_fc, alpha=0.88, height=0.65)
for i, (_, row) in enumerate(type_stats.iterrows()):
    ax.text(row['night_rate'] + 1.2, i,
            f"  {row['night_rate']:.1f}%  ({int(row['night']):,}/{int(row['total']):,})",
            va='center', fontsize=10, color='#333')
ax.set_yticks(y_pos)
ax.set_yticklabels(type_stats['facility_type'], fontsize=10)
ax.set_xlabel('Night Service Rate (%)', fontsize=11)
ax.set_title('(a) Night Service Coverage by Facility Type', fontweight='bold', fontsize=13)
ax.axvline(x=50, color='gray', ls='--', alpha=0.5, lw=1.5, label='50% threshold')
ax.axvline(x=30, color='orange', ls='--', alpha=0.5, lw=1.5, label='30% threshold')
ax.set_xlim(0, 118)
ax.grid(axis='x', alpha=0.3)
ax.legend(fontsize=10, loc='lower right')

ax = axes[1]
top_saii = gdf.nlargest(15, 'SAII').sort_values('SAII')
c = ['#d73027' if s > 0.04 else '#f46d43' if s > 0.02 else '#fdae61'
     for s in top_saii['SAII']]
ax.barh(np.arange(len(top_saii)), top_saii['SAII'], color=c, alpha=0.88, height=0.65)
labels = [f"ID {int(r['community_id'])} ({int(r['population']):,}pop)" for _, r in top_saii.iterrows()]
ax.set_yticks(np.arange(len(top_saii)))
ax.set_yticklabels(labels, fontsize=10)
ax.set_xlabel('SAII Score', fontsize=11)
ax.set_title('(b) Top 15 Accessibility Illusion Communities', fontweight='bold', fontsize=13)
ax.grid(axis='x', alpha=0.3)
ax.invert_yaxis()
for i, (_, row) in enumerate(top_saii.iterrows()):
    ax.text(row['SAII']+0.001, i,
            f"  SAII:{row['SAII']:.3f}  TPI:{row['TPI']:.1f}%",
            va='center', fontsize=10)

plt.suptitle('Figure 4: Night Service Supply-Demand Analysis', fontsize=14, fontweight='bold', y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(BASE, 'p8_fig4_night_service.png'), dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print("  [OK] p8_fig4_night_service.png")

print("\n[Fig5] Comprehensive conclusion...")
fig = plt.figure(figsize=(20, 13))

ax1 = fig.add_subplot(2, 3, (1, 4))
tpi_v = gdf_proj['TPI'].values
sc = ax1.scatter(gdf_proj.geometry.x, gdf_proj.geometry.y,
                c=tpi_v, cmap=TPI_CMAP, s=gdf_proj['population']/200+20,
                alpha=0.85, edgecolors='white', linewidths=0.4, norm=TPI_NORM)
road_proj.plot(ax=ax1, color='#cccccc', linewidth=0.12, alpha=0.3)
cbar = plt.colorbar(sc, ax=ax1, shrink=0.85, pad=0.015)
cbar.set_label('TPI (%)', fontsize=11)
cbar.ax.tick_params(labelsize=9)
ax1.set_xlim(road_proj.total_bounds[0]-150, road_proj.total_bounds[2]+150)
ax1.set_ylim(road_proj.total_bounds[1]-150, road_proj.total_bounds[3]+150)
ax1.set_xlabel('Longitude (Web Mercator)', fontsize=11)
ax1.set_ylabel('Latitude (Web Mercator)', fontsize=11)
ax1.set_title('Time Poverty Index (TPI) Spatial Distribution', fontweight='bold', fontsize=14)
ax1.grid(True, alpha=0.1)

handles = [
    mpatches.Patch(facecolor='#d73027', label='Severe Depriv. (TPI>=50%)'),
    mpatches.Patch(facecolor='#f46d43', label='Moderate (20%-50%)'),
    mpatches.Patch(facecolor='#fdae61', label='Mild (5%-20%)'),
    mpatches.Patch(facecolor='#fee08b', label='No Significant Gap (-5%~5%)'),
    mpatches.Patch(facecolor='#91cf60', label='Night Advantage (-20%~-5%)'),
    mpatches.Patch(facecolor='#1a9850', label='Strong Night Adv. (<-20%)'),
]
ax1.legend(handles=handles, fontsize=9, loc='upper left', framealpha=0.9,
          title='TPI Level', title_fontsize=10)

severe_pts = gdf_proj[gdf_proj['TPI'] > 100]
for _, row in severe_pts.iterrows():
    ax1.scatter(row.geometry.x, row.geometry.y, facecolors='none',
                edgecolors='darkred', s=300, linewidths=2.5)
    ax1.annotate(f"C{int(row['community_id'])}\nPop:{int(row['population']/1000):.0f}K\nTPI:{row['TPI']:.0f}%",
                 (row.geometry.x+300, row.geometry.y+300), fontsize=8.5,
                 color='darkred', fontweight='bold')

ax2 = fig.add_subplot(2, 3, 2)
level_order = ['4-Severe', '3-Moderate', '2-Mild', '1-None', '0-NightAdv']
level_colors = ['#d73027', '#f46d43', '#fdae61', '#fee08b', '#1a9850']
level_pop_sum = [gdf[gdf['TPI_level']==lv]['population'].sum() for lv in level_order]
short_labels = ['Severe Depriv.', 'Moderate Depriv.', 'Mild Depriv.', 'No Sig. Gap', 'Night Adv.']
wedges, texts, autotexts = ax2.pie(level_pop_sum, labels=short_labels, autopct='%1.1f%%',
                                    colors=level_colors, startangle=90, pctdistance=0.72,
                                    textprops={'fontsize': 10})
for at in autotexts:
    at.set_fontweight('bold')
    at.set_fontsize(11)
for t in texts:
    t.set_fontsize(10)
ax2.set_title('Population by TPI Level', fontweight='bold', fontsize=13)
total_affected = sum(level_pop_sum[:3])
note_text = (f'Night-deprived: {total_affected/1e4:.1f}K / {total_pop/1e4:.2f}M\n'
             f'  = {100*total_affected/total_pop:.1f}% of total population')
ax2.text(0, -1.38, note_text, fontsize=11, ha='center',
         bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))

ax3 = fig.add_subplot(2, 3, 3)
sorted_g = gdf.sort_values('A_day_norm')
x_i = np.arange(len(sorted_g))
ax3.fill_between(x_i, sorted_g['A_day_norm'], alpha=0.15, color='green')
ax3.fill_between(x_i, sorted_g['A_night_norm'], alpha=0.15, color='blue')
ax3.plot(x_i, sorted_g['A_day_norm'], color='green', lw=1.8, alpha=0.9, label='Day Accessibility')
ax3.plot(x_i, sorted_g['A_night_norm'], color='blue', lw=1.8, alpha=0.9, label='Night Accessibility')
ax3.set_xlabel('Community Rank (sorted by Day Accessibility)', fontsize=11)
ax3.set_ylabel('Normalized Accessibility', fontsize=11)
ax3.set_title('Accessibility Gap Profile', fontweight='bold', fontsize=13)
ax3.legend(fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.set_xlim(0, len(sorted_g))

ax4 = fig.add_subplot(2, 3, 5)
if 'community_type' in gdf.columns:
    type_tpi = gdf.groupby('community_type').apply(
        lambda x: pd.Series({
            'wmean': (x['TPI']*x['population']).sum()/x['population'].sum(),
            'pop': x['population'].sum()
        })).reset_index().sort_values('wmean')
    c_ct = ['#d73027' if v < -30 else '#f46d43' if v < 0 else '#1a9850' for v in type_tpi['wmean']]
    ax4.barh(type_tpi['community_type'], type_tpi['wmean'], color=c_ct, alpha=0.88, height=0.6)
    for i, (_, row) in enumerate(type_tpi.iterrows()):
        va = 'bottom' if row['wmean'] >= 0 else 'top'
        off = 4 if row['wmean'] >= 0 else -4
        ax4.text(row['wmean']+off, i, f"  {row['wmean']:.1f}%  ({int(row['pop']/1000):,}K)",
                 va=va, fontsize=10)
    ax4.axvline(x=0, color='black', ls='--', alpha=0.6, lw=1.5)
    ax4.set_xlabel('Population-Weighted Mean TPI (%)', fontsize=11)
    ax4.set_title('TPI by Community Type', fontweight='bold', fontsize=13)
    ax4.grid(axis='x', alpha=0.3)

ax5 = fig.add_subplot(2, 3, 6)
top_gap = type_stats.nsmallest(8, 'night_rate')
gap_v = 100 - top_gap['night_rate']
c_gap = ['#d73027' if v > 80 else '#f46d43' if v > 50 else '#fdae61' for v in gap_v]
ax5.barh(np.arange(len(top_gap)), gap_v, color=c_gap, alpha=0.88, height=0.6)
ax5.set_yticks(np.arange(len(top_gap)))
ax5.set_yticklabels(top_gap['facility_type'], fontsize=10)
ax5.set_xlabel('Night Service Gap (%)', fontsize=11)
ax5.set_title('Critical Night Service Gaps', fontweight='bold', fontsize=13)
ax5.grid(axis='x', alpha=0.3)
ax5.set_xlim(0, 115)
for i, (_, row) in enumerate(top_gap.iterrows()):
    ax5.text(100-row['night_rate']+1.5, i, f"  {100-row['night_rate']:.1f}%",
             va='center', fontsize=10)

day_poi = len(poi_df)
night_poi = poi_df['night_service_final'].sum()
plt.suptitle(
    'Figure 5: Accessibility Illusion Analysis - Nanshan District, Shenzhen\n'
    f'Population: {total_pop/1e4:.2f}M ({NS_YEAR}) | Source: {NS_POP_SOURCE} | '
    f'Road Network: {G.number_of_edges():,} roads | Day POI: {day_poi:,} | Night POI: {int(night_poi):,}',
    fontsize=13, fontweight='bold', y=1.015
)
plt.tight_layout()
fig.savefig(os.path.join(BASE, 'p8_fig5_conclusion.png'), dpi=200, bbox_inches='tight', facecolor='white')
plt.close()
print("  [OK] p8_fig5_conclusion.png")

print("\n" + "=" * 70)
print("DONE - 5 figures generated")
print("=" * 70)
print(f"Communities: {len(gdf)}, Total pop: {total_pop:,} ({total_pop/1e4:.2f}M)")
print(f"Road network: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")
print(f"POI: {day_poi:,} total, {int(night_poi):,} night service")
print(f"\nKey AII statistics:")
print(f"  Mean TPI: {gdf['TPI'].mean():.2f}%")
print(f"  Median TPI: {gdf['TPI'].median():.2f}%")
print(f"  Night-deprived communities (TPI>5): {len(dep)}/{len(gdf)} ({100*len(dep)/len(gdf):.1f}%)")
print(f"  Night-deprived population: {dep_pop/1e4:.1f}K ({100*dep_pop/total_pop:.1f}%)")
print(f"  Day accessibility mean: {gdf['A_day_norm'].mean():.4f}")
print(f"  Night accessibility mean: {gdf['A_night_norm'].mean():.4f}")
print(f"  Accessibility gap: {gdf['accessibility_gap'].mean():.4f}")
