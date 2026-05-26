# -*- coding: utf-8 -*-
"""
P1: 从 OSM 获取南山区建筑轮廓 (building footprints)
作为居住小区的真实 AOI 替代合成点数据
策略：
  1. 用 osmnx 直接从 Overpass API 下载 building=* 数据（南山区 bbox）
  2. 过滤 residential/apartments 建筑
  3. 与 villages.db 的合成小区叠加（取最近建筑匹配）
  4. 生成 GeoJSON 用于 Folium 底图
"""
import geopandas as gpd, pandas as pd, osmnx as ox, os, sys, io, time, json
import numpy as np, matplotlib.pyplot as plt
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ox.settings.use_cache = True
ox.settings.log_console = False

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT  = BASE + r"\osm_data"
BUILD_DIR = BASE + r"\building_data"
os.makedirs(BUILD_DIR, exist_ok=True)

# 南山区 bounding box (WGS84)
NS_BBOX = (22.45, 22.65, 113.85, 114.45)  # (south, north, west, east)

print("=" * 70)
print("P1: 获取南山区 OSM 建筑轮廓")
print("=" * 70)

# ── Step 1: 尝试从缓存加载或下载 ──
cache_geojson = os.path.join(BUILD_DIR, "nanshan_buildings.geojson")
cache_gpkg    = os.path.join(BUILD_DIR, "nanshan_buildings.gpkg")

if os.path.exists(cache_geojson):
    print(f"\n从缓存加载: {cache_geojson}")
    gdf = gpd.read_file(cache_geojson)
    print(f"已加载 {len(gdf):,} 个建筑")
else:
    print("\n从 OSM Overpass API 下载建筑数据...")
    print("  这可能需要 1-3 分钟（取决于网络）...")
    
    try:
        t0 = time.time()
        # 使用 tags 过滤建筑
        tags = {
            "building": ["residential", "apartments", "house", "dormitory",
                        "detached", "terrace", "commercial", "office",
                        "retail", "warehouse", "industrial"],
        }
        gdf = ox.features_from_bbox(bbox=NS_BBOX, tags=tags)
        print(f"  下载完成，耗时 {time.time()-t0:.0f}s")
        print(f"  获取 {len(gdf):,} 个 OSM 建筑要素")
        
        # 只保留面（Polygon/MultiPolygon）
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon","MultiPolygon"])].copy()
        gdf = gdf.reset_index(drop=True)
        print(f"  面要素: {len(gdf):,}")
        
        # 保存
        gdf.to_file(cache_geojson, driver="GeoJSON", encoding="utf-8")
        gdf.to_file(cache_gpkg, driver="GPKG", encoding="utf-8")
        print(f"  ✓ 已保存: {cache_geojson}")
        print(f"  ✓ 已保存: {cache_gpkg}")
        
    except Exception as e:
        print(f"  下载失败: {e}")
        print("  尝试备用方案：使用已有路网 POI 数据的中心点范围...")
        gdf = None

# ── Step 2: 建筑数据质量分析 ──
if gdf is not None and len(gdf) > 0:
    print(f"\n{'='*60}")
    print(f"建筑数据质量报告")
    print(f"{'='*60}")
    print(f"  总建筑数: {len(gdf):,}")
    
    # 面积统计
    gdf_proj = gdf.to_crs("EPSG:32650")  # UTM zone 50N
    gdf_proj["area_m2"] = gdf_proj.geometry.area
    gdf_proj["area_ha"]  = gdf_proj["area_m2"] / 10000
    
    print(f"\n  面积统计:")
    print(f"    均值: {gdf_proj['area_m2'].mean():.0f} m²")
    print(f"    中位数: {gdf_proj['area_m2'].median():.0f} m²")
    print(f"    最大: {gdf_proj['area_m2'].max():.0f} m²")
    print(f"    最小: {gdf_proj['area_m2'].min():.0f} m²")
    
    # 居住建筑 vs 商业
    gdf_proj["bldg_type"] = gdf_proj.get("building", pd.Series(["unknown"]*len(gdf_proj)))
    bldg_vc = gdf_proj["bldg_type"].value_counts().head(10)
    print(f"\n  建筑类型分布 (Top 10):")
    for bt, cnt in bldg_vc.items():
        print(f"    {bt}: {cnt:,}")
    
    # 南山区范围的居住建筑
    res_bldg = gdf_proj[gdf_proj["bldg_type"].isin(
        ["residential","apartments","house","dormitory","detached","terrace"])]
    print(f"\n  居住类建筑: {len(res_bldg):,} 个")
    print(f"    总面积: {res_bldg['area_ha'].sum():.1f} ha")
    
    # 与合成小区的叠加
    print(f"\n{'='*60}")
    print(f"建筑轮廓 vs 合成小区叠加")
    print(f"{'='*60}")
    
    # 加载合成小区
    conn = __import__('sqlite3').connect(f"{BASE}\\village_data\\villages.db")
    villages = pd.read_sql("SELECT * FROM sz_village", conn)
    conn.close()
    v_gdf = gpd.GeoDataFrame(
        villages,
        geometry=gpd.points_from_xy(villages["lng"], villages["lat"]),
        crs="EPSG:4326"
    )
    
    # 为每个合成小区找到最近的 OSM 建筑
    from scipy.spatial import cKDTree
    v_coords = np.array([(r.lng, r.lat) for _, r in villages.iterrows()])
    bldg_centroids = np.array([(g.centroid.x, g.centroid.y) 
                                  for g in gdf_proj.geometry])
    tree = cKDTree(bldg_centroids)
    dists, idxs = tree.query(v_coords)
    
    # 统计最近建筑的距离
    print(f"  小区数: {len(villages):,}")
    print(f"  有100m内建筑: {(dists < 0.001).sum():,} ({(dists < 0.001).mean()*100:.1f}%)")
    print(f"  有200m内建筑: {(dists < 0.002).sum():,} ({(dists < 0.002).mean()*100:.1f}%)")
    print(f"  无匹配建筑: {(dists > 0.01).sum():,}")
    
    # 为合成小区赋予最近建筑的 AOI 面积
    nearest_area = np.array([gdf_proj.iloc[idx]["area_m2"] if idx < len(gdf_proj) else np.nan
                              for idx in idxs])
    nearest_btype = np.array([gdf_proj.iloc[idx]["bldg_type"] if idx < len(gdf_proj) else "none"
                               for idx in idxs])
    villages["nearest_building_area_m2"] = nearest_area
    villages["nearest_building_type"]     = nearest_btype
    villages["nearest_building_dist_deg"]  = dists
    
    # 覆盖率统计
    res_match = (nearest_btype.isin(["residential","apartments","house","dormitory"])).sum()
    print(f"\n  匹配为居住类建筑: {res_match:,} ({100*res_match/len(villages):.1f}%)")
    
    # 保存带建筑属性的合成小区
    out_villages = OUT + r"\nanshan_villages_with_building.csv"
    villages.to_csv(out_villages, index=False, encoding="utf-8")
    print(f"\n  ✓ 已保存: {out_villages}")
    
    # ── Step 3: 可视化预览 ──
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    # 左图：建筑分布
    ax = axes[0]
    gdf_proj.plot(ax=ax, column="bldg_type", 
                  cmap="Set3", alpha=0.6, legend=True, 
                  legend_kwds={"loc":"lower right","fontsize":7})
    ax.set_title(f"南山区 OSM 建筑分布\n(共 {len(gdf_proj):,} 个建筑)", fontsize=11)
    ax.set_xlabel("经度")
    ax.set_ylabel("纬度")
    
    # 右图：居住建筑 vs 合成小区
    ax2 = axes[1]
    res_only = gdf_proj[gdf_proj["bldg_type"].isin(["residential","apartments","house"])]
    res_only.plot(ax=ax2, color="#27ae60", alpha=0.5, label="居住建筑")
    gpd.GeoDataFrame(villages.assign(geometry=gpd.points_from_xy(villages.lng, villages.lat)),
                      crs="EPSG:4326").plot(ax=ax2, color="red", markersize=3, alpha=0.7, label="合成小区")
    ax2.set_title("居住建筑 + 合成小区叠加", fontsize=11)
    ax2.legend()
    
    plt.tight_layout()
    fig.savefig(os.path.join(BUILD_DIR, "nanshan_buildings_preview.png"), dpi=150, bbox_inches="tight")
    print(f"\n  ✓ 预览图已保存: {BUILD_DIR}\\nanshan_buildings_preview.png")
    
    # ── Step 4: 生成用于 notebook 的 GeoJSON ──
    # 选择有意义的居住建筑
    keep_types = ["residential","apartments","house","dormitory","terrace","detached"]
    meaningful = gdf_proj[gdf_proj["bldg_type"].isin(keep_types)].copy()
    meaningful = meaningful[meaningful["area_m2"] > 50]  # 过滤过小碎片
    
    out_geojson = BUILD_DIR + r"\nanshan_residential_buildings.geojson"
    meaningful.to_file(out_geojson, driver="GeoJSON", encoding="utf-8")
    print(f"\n  ✓ 居住建筑 GeoJSON: {out_geojson}")
    print(f"    共 {len(meaningful):,} 个，总面积 {meaningful['area_ha'].sum():.1f} ha")
    
    # 统计摘要
    print(f"\n{'='*60}")
    print(f"最终居住建筑统计")
    print(f"{'='*60}")
    print(f"  总建筑: {len(meaningful):,}")
    print(f"  总面积: {meaningful['area_ha'].sum():.1f} ha ({meaningful['area_m2'].sum()/1e6:.2f} km²)")
    print(f"  均值面积: {meaningful['area_m2'].mean():.0f} m²")
    print(f"  南山区面积估算: ~{120:.0f} km² → 居住建筑覆盖率 ~{meaningful['area_m2'].sum()/1e6/120*100:.1f}%")
    
else:
    print("无法获取 OSM 建筑数据，将使用现有合成小区继续分析")
