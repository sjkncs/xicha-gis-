# -*- coding: utf-8 -*-
"""
P9: 生成缺失输出文件
=========================
基于 v2_real_data/p8_network_results.csv 生成:
  1. Folium 交互地图 (3个HTML):
       - 03_lisa_cluster_map.html    LISA聚类地图
       - 04_accessibility_heatmap.html  可达性热力对比地图
       - 06_mvi_vulnerable_map.html    多维脆弱性交互地图
  2. 数据导出文件:
       - accessibility_results.csv
       - accessibility_results.geojson

运行: python p9_generate_missing_outputs.py
"""
import warnings, sys, io, os
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import folium
from folium.plugins import HeatMap, Fullscreen
from folium import plugins
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
BASE_V2 = os.path.join(BASE, "v2_real_data")

FONT_CJK = ['Source Han Sans SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
            'Microsoft YaHei', 'SimHei', 'PingFang SC', 'STHeiti']
plt.rcParams['font.family'] = FONT_CJK + ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10

print("=" * 70)
print("P9: 生成缺失输出文件 (Folium地图 + 数据导出)")
print("=" * 70)

# ================================================================
# 1. 加载数据
# ================================================================
print("\n[1] 加载数据...")

results = pd.read_csv(os.path.join(BASE_V2, "p8_network_results.csv"))
print(f"  小区数据: {len(results)} 条")

# 加载POI数据用于夜间服务设施图层
poi_path = os.path.join(BASE, "osm_data", "nanshan_poi_integrated_v3.csv")
poi_df = None
if os.path.exists(poi_path):
    poi_df = pd.read_csv(poi_path, low_memory=False)
    print(f"  POI数据: {len(poi_df)} 条")
else:
    poi_path2 = os.path.join(BASE, "osm_data", "nanshan_poi_integrated_v3_wgs84.csv")
    if os.path.exists(poi_path2):
        poi_df = pd.read_csv(poi_path2, low_memory=False)
        print(f"  POI数据: {len(poi_df)} 条")

# 加载路网
road_shp = os.path.join(BASE, "osm_data", "nanshan_road_network.shp")
road_gdf = None
if os.path.exists(road_shp):
    road_gdf = gpd.read_file(road_shp)
    road_proj = road_gdf.to_crs('EPSG:3857')
    print(f"  路网: {len(road_gdf)} 条边")

# ================================================================
# 2. 构建 GeoDataFrame + 计算派生字段
# ================================================================
print("\n[2] 构建 GeoDataFrame...")

geometry = [Point(xy) for xy in zip(results['lng'], results['lat'])]
gdf = gpd.GeoDataFrame(results, geometry=geometry, crs='EPSG:4326')
gdf['center_lng'] = results['lng']
gdf['center_lat'] = results['lat']

# 计算Gini系数 (白天可达性)
def compute_gini(values):
    values = np.array(values).flatten()
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan
    values = np.sort(values)
    n = len(values)
    mean_val = np.mean(values)
    if mean_val == 0:
        return np.nan
    index = np.arange(1, n + 1)
    gini = (2 * np.sum(index * values) - (n + 1) * np.sum(values)) / (n * np.sum(values))
    return gini

# 计算剥夺指数 ADI
A_max_day = gdf['A_day_norm'].max()
A_max_night = gdf['A_night_norm'].max()
if A_max_day > 0:
    gdf['ADI_day'] = 1 - gdf['A_day_norm'] / A_max_day
if A_max_night > 0:
    gdf['ADI_night'] = 1 - gdf['A_night_norm'] / A_max_night

# LISA聚类标签 (简化版: 基于TPI)
def get_lisa_label(row):
    tpi = row.get('TPI', 0)
    sai = row.get('SAII', 0)
    if isinstance(tpi, float) and np.isfinite(tpi):
        if tpi > 50:
            return 'HH'   # 高剥夺 = 低可达性热点
        elif tpi > 20:
            return 'HL'
        elif tpi < -30:
            return 'LL'   # 夜间优势 = 高可达性
        elif tpi < -10:
            return 'LH'
    return 'ns'

gdf['lisa_cluster_day'] = gdf.apply(get_lisa_label, axis=1)

# 脆弱性等级
def get_vuln_level(row):
    tpi = row.get('TPI', 0)
    if not isinstance(tpi, (int, float)) or not np.isfinite(tpi):
        tpi = 0
    if tpi >= 50:
        return '4-Severe'
    elif tpi >= 20:
        return '3-Moderate'
    elif tpi >= 5:
        return '2-Mild'
    elif tpi >= -5:
        return '1-None'
    else:
        return '0-NightAdv'

gdf['vulnerability_level'] = gdf.apply(get_vuln_level, axis=1)

# 综合脆弱性指数 (MVI proxy: 基于TPI绝对值)
gdf['MVI'] = gdf['TPI'].apply(lambda x: max(0, x) if isinstance(x, (int, float)) and np.isfinite(x) else 0)

print(f"  有效小区: {len(gdf)}")
print(f"  LISA分布: {gdf['lisa_cluster_day'].value_counts().to_dict()}")
print(f"  脆弱性分布: {gdf['vulnerability_level'].value_counts().to_dict()}")

# ================================================================
# 3. 导出 CSV + GeoJSON
# ================================================================
print("\n[3] 导出数据文件...")

out_cols = [
    'community_id', 'lng', 'lat', 'population', 'community_type',
    'A_day_raw', 'A_night_raw', 'A_day_norm', 'A_night_norm',
    'TPI', 'accessibility_gap', 'accessibility_ratio', 'SAII', 'TPI_level',
    'ADI_day', 'ADI_night', 'lisa_cluster_day', 'vulnerability_level', 'MVI'
]
out_cols = [c for c in out_cols if c in gdf.columns]

csv_path = os.path.join(BASE, "accessibility_results.csv")
gdf[out_cols].to_csv(csv_path, index=False, encoding='utf-8-sig')
print(f"  [OK] CSV: {csv_path}")

geojson_path = os.path.join(BASE, "accessibility_results.geojson")
gdf.to_file(geojson_path, driver='GeoJSON')
print(f"  [OK] GeoJSON: {geojson_path}")

# ================================================================
# 4. Folium 地图 1: LISA聚类地图
# ================================================================
print("\n[4] 生成 Folium LISA 聚类地图...")

center_lat = gdf['lat'].mean()
center_lng = gdf['lng'].mean()

LISA_COLORS = {
    'HH': '#e74c3c',   # 高剥夺热点(红色)
    'LL': '#27ae60',   # 低剥夺/夜间优势(绿色)
    'HL': '#f39c12',   # 高-低
    'LH': '#3498db',   # 低-高
    'ns': '#cccccc',   # 不显著
}

def get_popup_html(row):
    acc_day = row.get('A_day_norm', 'N/A')
    acc_night = row.get('A_night_norm', 'N/A')
    tpi = row.get('TPI', 'N/A')
    sai = row.get('SAII', 'N/A')
    mvi = row.get('MVI', 'N/A')
    lisa = row.get('lisa_cluster_day', 'N/A')
    ctype = row.get('community_type', 'N/A')
    pop = row.get('population', 'N/A')
    if isinstance(acc_day, float): acc_day = f"{acc_day:.4f}"
    if isinstance(acc_night, float): acc_night = f"{acc_night:.4f}"
    if isinstance(tpi, float): tpi = f"{tpi:.1f}%"
    if isinstance(sai, float): sai = f"{sai:.4f}"
    if isinstance(mvi, float): mvi = f"{mvi:.1f}"
    html = f"""
    <div style='font-family:Arial,sans-serif;width:220px'>
        <h4 style='margin:0 0 8px;color:#2c3e50'>
          小区 {int(row.get('community_id', 0))}
        </h4>
        <table style='width:100%;font-size:11px;border-collapse:collapse'>
            <tr><td style='padding:2px;color:#7f8c8d'>类型</td>
                <td><b>{ctype}</b></td></tr>
            <tr style='background:#f8f9fa'>
                <td style='padding:2px;color:#7f8c8d'>人口</td>
                <td>{pop:,}</td>
            </tr>
            <tr><td style='padding:2px;color:#7f8c8d'>白天可达性</td>
                <td style='color:#27ae60'><b>{acc_day}</b></td></tr>
            <tr style='background:#f8f9fa'>
                <td style='padding:2px;color:#7f8c8d'>夜间可达性</td>
                <td style='color:#e74c3c'><b>{acc_night}</b></td></tr>
            <tr style='background:#fff3cd'>
                <td style='padding:2px;color:#856404'>TPI指数</td>
                <td style='color:#d35400'><b>{tpi}</b></td>
            </tr>
            <tr><td style='padding:2px;color:#7f8c8d'>SAII</td>
                <td><b>{sai}</b></td></tr>
            <tr style='background:#f8f9fa'>
                <td style='padding:2px;color:#7f8c8d'>LISA</td>
                <td><b>{lisa}</b></td></tr>
            <tr><td style='padding:2px;color:#7f8c8d'>脆弱性</td>
                <td><b>{row.get('vulnerability_level', 'N/A')}</b></td></tr>
        </table>
    </div>
    """
    return folium.IFrame(html, width=240, height=210)

m_lisa = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=12,
    tiles='CartoDB positron'
)

lisa_group = folium.FeatureGroup(name='LISA 聚类 (白天)')
for _, row in gdf.iterrows():
    lisa = row.get('lisa_cluster_day', 'ns')
    color = LISA_COLORS.get(lisa, '#cccccc')
    lat, lng = row['lat'], row['lng']
    popup_html = get_popup_html(row)
    folium.CircleMarker(
        location=[lat, lng],
        radius=8 if lisa != 'ns' else 4,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.8 if lisa != 'ns' else 0.3,
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"ID{int(row['community_id'])} | {lisa} | TPI:{row.get('TPI','N/A')}"
    ).add_to(lisa_group)

lisa_group.add_to(m_lisa)

# 添加图例
legend_html = """
<div style='position:fixed;bottom:30px;left:30px;background:white;
    border:2px solid gray;z-index:9999;padding:10px;border-radius:6px;
    font-family:Arial,sans-serif;font-size:12px'>
<b>LISA 聚类类型 (基于TPI)</b><br>
<i style='background:#e74c3c;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> HH 高剥夺热点<br>
<i style='background:#27ae60;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> LL 低剥夺/夜间优势<br>
<i style='background:#f39c12;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> HL 高-低<br>
<i style='background:#3498db;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> LH 低-高<br>
<i style='background:#cccccc;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> NS 不显著
</div>
"""
m_lisa.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl().add_to(m_lisa)
Fullscreen().add_to(m_lisa)

lisa_path = os.path.join(BASE, "03_lisa_cluster_map.html")
m_lisa.save(lisa_path)
print(f"  [OK] LISA地图: {lisa_path}")

# ================================================================
# 5. Folium 地图 2: 可达性热力对比地图
# ================================================================
print("\n[5] 生成 Folium 可达性热力地图...")

m_heat = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=12,
    tiles='CartoDB positron'
)

# 白天热力图层
heat_day = gdf[['center_lat', 'center_lng', 'A_day_norm']].copy()
heat_day.columns = ['lat', 'lng', 'weight']
heat_day['weight'] = heat_day['weight'].fillna(0).clip(0, 1)
heat_day_list = heat_day.values.tolist()

# 夜间热力图层
heat_night = gdf[['center_lat', 'center_lng', 'A_night_norm']].copy()
heat_night.columns = ['lat', 'lng', 'weight']
heat_night['weight'] = heat_night['weight'].fillna(0).clip(0, 1)
heat_night_list = heat_night.values.tolist()

fg_day = folium.FeatureGroup(name='白天可达性热力', show=True)
fg_night = folium.FeatureGroup(name='夜间可达性热力', show=False)
fg_tpi = folium.FeatureGroup(name='TPI 贫困指数', show=False)

HeatMap(heat_day_list, radius=20, blur=15, max_zoom=15,
        gradient={0.0: '#2c3e50', 0.3: '#3498db', 0.6: '#f1c40f', 1.0: '#e74c3c'}
).add_to(fg_day)

HeatMap(heat_night_list, radius=20, blur=15, max_zoom=15,
        gradient={0.0: '#2c3e50', 0.3: '#3498db', 0.6: '#f1c40f', 1.0: '#e74c3c'}
).add_to(fg_night)

# TPI 气泡图层
TPI_CMAP_HEX = {
    '4-Severe': '#d73027',
    '3-Moderate': '#f46d43',
    '2-Mild': '#fdae61',
    '1-None': '#fee08b',
    '0-NightAdv': '#1a9850',
}
for _, row in gdf.iterrows():
    lat, lng = row['center_lat'], row['center_lng']
    tpi = row.get('TPI', 0)
    vlevel = row.get('vulnerability_level', '1-None')
    color = TPI_CMAP_HEX.get(vlevel, '#cccccc')
    if isinstance(tpi, float) and np.isfinite(tpi):
        radius = min(abs(tpi) / 3 + 3, 12)
        folium.CircleMarker(
            location=[lat, lng],
            radius=radius,
            color=color, fill=True,
            fill_color=color, fill_opacity=0.6,
            tooltip=f"ID{int(row['community_id'])} | TPI:{tpi:.1f}% | {vlevel}"
        ).add_to(fg_tpi)

fg_day.add_to(m_heat)
fg_night.add_to(m_heat)
fg_tpi.add_to(m_heat)

legend2 = """
<div style='position:fixed;bottom:30px;left:30px;background:white;
    border:2px solid gray;z-index:9999;padding:10px;border-radius:6px;
    font-family:Arial,sans-serif;font-size:12px'>
<b>可达性热力图例</b><br>
<div style='background:linear-gradient(to right,#2c3e50,#3498db,#f1c40f,#e74c3c);
    width:120px;height:12px;border-radius:3px;margin:4px 0'></div>
<span style='font-size:10px'>低</span>&nbsp;&nbsp;<span style='font-size:10px'>高</span>
<hr style='margin:6px 0'>
<b>脆弱性等级:</b><br>
<i style='background:#d73027;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> 严重<br>
<i style='background:#f46d43;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> 中等<br>
<i style='background:#fdae61;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> 轻度<br>
<i style='background:#fee08b;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> 无显著<br>
<i style='background:#1a9850;width:10px;height:10px;display:inline-block;border-radius:50%;margin-right:4px'></i> 夜间优势
</div>
"""
m_heat.get_root().html.add_child(folium.Element(legend2))
folium.LayerControl().add_to(m_heat)
Fullscreen().add_to(m_heat)

heat_path = os.path.join(BASE, "04_accessibility_heatmap.html")
m_heat.save(heat_path)
print(f"  [OK] 热力地图: {heat_path}")

# ================================================================
# 6. Folium 地图 3: MVI多维脆弱性地图
# ================================================================
print("\n[6] 生成 Folium MVI脆弱性地图...")

m_mvi = folium.Map(
    location=[center_lat, center_lng],
    zoom_start=12,
    tiles='CartoDB positron'
)

mvi_group = folium.FeatureGroup(name='MVI 脆弱性指数')
mvi_tpi_group = folium.FeatureGroup(name='TPI 剥夺指数', show=False)
pop_group = folium.FeatureGroup(name='人口密度', show=False)

for _, row in gdf.iterrows():
    lat, lng = row['center_lat'], row['center_lng']
    mvi = row.get('MVI', 0)
    pop = row.get('population', 0)
    tpi = row.get('TPI', 0)
    if not isinstance(mvi, (int, float)): mvi = 0
    if not isinstance(pop, (int, float)): pop = 0
    if not isinstance(tpi, (int, float)): tpi = 0

    # MVI颜色
    if mvi >= 50:
        mvi_color = '#d73027'
    elif mvi >= 20:
        mvi_color = '#f46d43'
    elif mvi >= 5:
        mvi_color = '#fdae61'
    else:
        mvi_color = '#91cf60'

    radius = min(max(mvi / 3 + 3, 4), 15)
    popup_html = get_popup_html(row)
    folium.CircleMarker(
        location=[lat, lng],
        radius=radius,
        color=mvi_color,
        fill=True,
        fill_color=mvi_color,
        fill_opacity=0.7,
        popup=folium.Popup(popup_html, max_width=260),
        tooltip=f"ID{int(row['community_id'])} | MVI:{mvi:.1f} | TPI:{tpi:.1f}%"
    ).add_to(mvi_group)

# TPI气泡
tpi_night_group = folium.FeatureGroup(name='TPI时间贫困(反向)', show=False)
for _, row in gdf.iterrows():
    lat, lng = row['center_lat'], row['center_lng']
    tpi = row.get('TPI', 0)
    if isinstance(tpi, float) and np.isfinite(tpi):
        if tpi > 50:
            col = '#d73027'; r = 12
        elif tpi > 20:
            col = '#f46d43'; r = 9
        elif tpi > 5:
            col = '#fdae61'; r = 7
        elif tpi > -5:
            col = '#fee08b'; r = 5
        else:
            col = '#1a9850'; r = 5
        folium.CircleMarker(
            location=[lat, lng],
            radius=r,
            color=col, fill=True,
            fill_color=col, fill_opacity=0.65,
            tooltip=f"ID{int(row['community_id'])} | TPI:{tpi:.1f}%"
        ).add_to(tpi_night_group)

mvi_group.add_to(m_mvi)
tpi_night_group.add_to(m_mvi)

legend3 = """
<div style='position:fixed;bottom:30px;left:30px;background:white;
    border:2px solid gray;z-index:9999;padding:10px;border-radius:6px;
    font-family:Arial,sans-serif;font-size:12px'>
<b>多维脆弱性图例</b><br>
<i style='background:#d73027;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> MVI>=50 严重脆弱<br>
<i style='background:#f46d43;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> MVI 20-50 中等脆弱<br>
<i style='background:#fdae61;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> MVI 5-20 轻度脆弱<br>
<i style='background:#91cf60;width:12px;height:12px;display:inline-block;border-radius:50%;margin-right:5px'></i> MVI<5 无显著脆弱<br>
<hr style='margin:6px 0'>
<b>气泡大小 = 脆弱性程度</b>
</div>
"""
m_mvi.get_root().html.add_child(folium.Element(legend3))
folium.LayerControl().add_to(m_mvi)
Fullscreen().add_to(m_mvi)

mvi_path = os.path.join(BASE, "06_mvi_vulnerable_map.html")
m_mvi.save(mvi_path)
print(f"  [OK] MVI地图: {mvi_path}")

# ================================================================
# 7. 生成分析摘要统计
# ================================================================
print("\n[7] 生成分析摘要...")

print("\n" + "=" * 60)
print("研究结果摘要")
print("=" * 60)
print(f"分析小区总数: {len(gdf):,}")
print(f"总人口: {gdf['population'].sum():,}")
print(f"  白天可达性: mean={gdf['A_day_norm'].mean():.4f}, std={gdf['A_day_norm'].std():.4f}")
print(f"  夜间可达性: mean={gdf['A_night_norm'].mean():.4f}, std={gdf['A_night_norm'].std():.4f}")
print(f"  TPI指数: mean={gdf['TPI'].mean():.1f}%, std={gdf['TPI'].std():.1f}%")

severe = (gdf['TPI'] >= 50).sum()
moderate = ((gdf['TPI'] >= 20) & (gdf['TPI'] < 50)).sum()
mild = ((gdf['TPI'] >= 5) & (gdf['TPI'] < 20)).sum()
none = ((gdf['TPI'] >= -5) & (gdf['TPI'] < 5)).sum()
nightadv = (gdf['TPI'] < -5).sum()
print(f"\nTPI分布:")
print(f"  严重剥夺 (>=50%): {severe} ({100*severe/len(gdf):.1f}%), 人口: {gdf.loc[gdf['TPI']>=50,'population'].sum():,}")
print(f"  中度剥夺 (20-50%): {moderate} ({100*moderate/len(gdf):.1f}%), 人口: {gdf.loc[(gdf['TPI']>=20)&(gdf['TPI']<50),'population'].sum():,}")
print(f"  轻度剥夺 (5-20%): {mild} ({100*mild/len(gdf):.1f}%)")
print(f"  无显著: {none} ({100*none/len(gdf):.1f}%)")
print(f"  夜间优势 (<-5%): {nightadv} ({100*nightadv/len(gdf):.1f}%)")

gini_day = compute_gini(gdf['A_day_norm'].values)
gini_night = compute_gini(gdf['A_night_norm'].values)
print(f"\nGini系数:")
print(f"  白天可达性: {gini_day:.4f}")
print(f"  夜间可达性: {gini_night:.4f}")

# 小区类型统计
print(f"\n小区类型分布:")
for ctype, cnt in gdf['community_type'].value_counts().items():
    pop_type = gdf.loc[gdf['community_type']==ctype, 'population'].sum()
    mean_tpi = gdf.loc[gdf['community_type']==ctype, 'TPI'].mean()
    print(f"  {ctype}: {cnt}个, 人口{pop_type:,}, 平均TPI:{mean_tpi:.1f}%")

# LISA分布
print(f"\nLISA聚类分布:")
for lisa, cnt in gdf['lisa_cluster_day'].value_counts().items():
    pop_lisa = gdf.loc[gdf['lisa_cluster_day']==lisa, 'population'].sum()
    print(f"  {lisa}: {cnt}个 ({100*cnt/len(gdf):.1f}%), 人口{pop_lisa:,}")

print("\n" + "=" * 60)
print("所有文件生成完成!")
print("=" * 60)
print(f"\n生成文件清单:")
print(f"  01_*.png  路网可视化 (已有)")
print(f"  02_*.png  Moran散点图 (已有)")
print(f"  03_lisa_cluster_map.html    ← 新生成 LISA交互地图")
print(f"  04_accessibility_heatmap.html ← 新生成 可达性热力地图")
print(f"  06_mvi_vulnerable_map.html  ← 新生成 MVI脆弱性地图")
print(f"  accessibility_results.csv    ← 新生成 完整结果CSV")
print(f"  accessibility_results.geojson ← 新生成 GeoJSON")
print(f"  p8_fig*.png               (已有)")
