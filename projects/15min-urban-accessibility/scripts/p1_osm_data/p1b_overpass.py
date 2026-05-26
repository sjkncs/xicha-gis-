# -*- coding: utf-8 -*-

"""

P1b: 用 Overpass API 直接获取南山区建筑数据

绕过 osmnx 的 geometry_from_bbox NaN 问题

"""

import requests, json, time, geopandas as gpd, pandas as pd, os

from shapely.geometry import shape, Polygon, MultiPolygon

import numpy as np, sys, io, matplotlib.pyplot as plt

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')



BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

OUT  = BASE + r"\osm_data"

BDIR = BASE + r"\building_data"

os.makedirs(BDIR, exist_ok=True)



# 南山区 bbox (lat_south, lat_north, lon_west, lon_east)

NS_SOUTH, NS_NORTH = 22.45, 22.55

NS_WEST,  NS_EAST  = 113.85, 114.05



print("=" * 70)

print("P1b: Overpass API 直接获取南山区建筑轮廓")

print("=" * 70)



# ── Overpass QL 查询 ──

# 南山区 bbox: (south, west, north, east)

overpass_query = f"""

[out:json][timeout:120];

(

  // 居住建筑

  way["building"="residential"]

    (22.45,113.85,22.55,114.05);

  way["building"="apartments"]

    (22.45,113.85,22.55,114.05);

  way["building"="house"]

    (22.45,113.85,22.55,114.05);

  way["building"="dormitory"]

    (22.45,113.85,22.55,114.05);

  way["building"="detached"]

    (22.45,113.85,22.55,114.05);

  // 商业/办公

  way["building"="commercial"]

    (22.45,113.85,22.55,114.05);

  way["building"="office"]

    (22.45,113.85,22.55,114.05);

  way["building"="retail"]

    (22.45,113.85,22.55,114.05);

  // 工业/仓储

  way["building"="warehouse"]

    (22.45,113.85,22.55,114.05);

  way["building"="industrial"]

    (22.45,113.85,22.55,114.05);

  // 公共

  way["building"="public"]

    (22.45,113.85,22.55,114.05);

  way["building"="government"]

    (22.45,113.85,22.55,114.05);

  // 其他常见建筑

  way["building"="yes"]

    (22.45,113.85,22.55,114.05);

  way["building"~"^(residential|house|apartments|dormitory|commercial|office|retail|industrial|warehouse|public|government)$"]

    (22.45,113.85,22.55,114.05);

);

out body geom;

"""



cache_file = os.path.join(BDIR, "overpass_response.json")



if os.path.exists(cache_file):

    print("从缓存加载 Overpass 响应...")

    with open(cache_file, encoding='utf-8') as f:

        raw = json.load(f)

else:

    print("正在从 Overpass API 获取建筑数据...")

    print("  南山区范围: lat {:.2f}-{:.2f}, lon {:.2f}-{:.2f}".format(

        NS_SOUTH, NS_NORTH, NS_WEST, NS_EAST))

    print("  这可能需要 1-2 分钟...")

    

    # 使用公共 Overpass 镜像

    url = "https://overpass-api.de/api/interpreter"

    # 也可尝试其他镜像

    mirrors = [

        "https://overpass-api.de/api/interpreter",

        "https://overpass.kumi.systems/api/interpreter",

        "https://z.overpass-api.de/api/interpreter",

    ]

    

    raw = None

    for attempt, mirror in enumerate(mirrors):

        try:

            print(f"\n  尝试镜像 {attempt+1}/{len(mirrors)}: {mirror}")

            t0 = time.time()

            resp = requests.post(

                mirror,

                data={"data": overpass_query},

                timeout=180

            )

            elapsed = time.time() - t0

            print(f"  响应时间: {elapsed:.0f}s, 状态: {resp.status_code}")

            if resp.status_code == 200:

                raw = resp.json()

                print(f"  成功! 获取 {len(raw.get('elements', []))} 个要素")

                break

            else:

                print(f"  失败: {resp.text[:200]}")

        except Exception as e:

            print(f"  异常: {e}")

    

    if raw is None:

        print("\n所有 Overpass 镜像均失败!")

        raw = {"elements": []}



    # 保存缓存

    with open(cache_file, 'w', encoding='utf-8') as f:

        json.dump(raw, f)



# ── 解析响应 ──

elements = raw.get("elements", [])

print(f"\n总共获取 {len(elements)} 个 OSM 要素")



# 构建 GeoDataFrame

records = []

no_geom = 0

for elem in elements:

    if elem.get("type") != "way":

        continue

    geom = elem.get("geometry")

    if not geom or len(geom) < 3:

        no_geom += 1

        continue

    

    try:

        coords = [(p["lon"], p["lat"]) for p in geom]

        if len(coords) >= 3:

            poly = Polygon(coords)

            if not poly.is_valid:

                poly = poly.buffer(0)

            records.append({

                "osm_id": elem.get("id"),

                "osm_type": elem.get("type"),

                "building": elem.get("tags", {}).get("building", "unknown"),

                "name": elem.get("tags", {}).get("name", ""),

                "height": elem.get("tags", {}).get("height", ""),

                "levels": elem.get("tags", {}).get("building:levels", ""),

                "geometry": poly

            })

    except Exception:

        continue



print(f"有效建筑记录: {len(records):,}")

if no_geom > 0:

    print(f"无几何信息: {no_geom}")



if len(records) == 0:

    print("没有获取到建筑数据!")

else:

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")

    print(f"\n建筑类型分布:")

    print(gdf["building"].value_counts().head(10).to_string())

    

    # ── 投影并计算面积 ──

    gdf_proj = gdf.to_crs("EPSG:32650")

    gdf_proj["area_m2"] = gdf_proj.geometry.area

    gdf_proj["area_ha"]  = gdf_proj["area_m2"] / 10000

    

    print(f"\n面积统计:")

    print(f"  总建筑: {len(gdf_proj):,}")

    print(f"  总面积: {gdf_proj['area_m2'].sum()/1e6:.2f} km²")

    print(f"  均值: {gdf_proj['area_m2'].mean():.0f} m²")

    print(f"  中位数: {gdf_proj['area_m2'].median():.0f} m²")

    

    # ── 居住建筑筛选 ──

    res_types = ["residential","apartments","house","dormitory","detached"]

    res_bldg = gdf_proj[gdf_proj["building"].isin(res_types)]

    print(f"\n居住类建筑: {len(res_bldg):,}")

    

    # ── 保存 ──

    out_geojson = os.path.join(BDIR, "nanshan_buildings_v2.geojson")

    out_gpkg    = os.path.join(BDIR, "nanshan_buildings_v2.gpkg")

    out_res_gj  = os.path.join(BDIR, "nanshan_residential_buildings.geojson")

    

    gdf_proj.to_file(out_geojson, driver="GeoJSON", encoding="utf-8")

    gdf_proj.to_file(out_gpkg, driver="GPKG", encoding="utf-8")

    

    res_bldg_wgs = res_bldg.to_crs("EPSG:4326")

    res_bldg_wgs.to_file(out_res_gj, driver="GeoJSON", encoding="utf-8")

    

    print(f"\n✓ 保存: {out_geojson}")

    print(f"✓ 保存: {out_gpkg}")

    print(f"✓ 保存: {out_res_gj} ({len(res_bldg):,} 居住建筑)")

    

    # ── 可视化 ──

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    

    ax = axes[0]

    gdf_proj.plot(ax=ax, column="building", cmap="Set3", alpha=0.6, legend=True,

                   legend_kwds={"loc":"lower right","fontsize":7})

    ax.set_title(f"Nanshan OSM Buildings\n{len(gdf_proj):,} buildings", fontsize=12)

    ax.set_xlabel("Lon"); ax.set_ylabel("Lat")

    

    ax2 = axes[1]

    res_bldg.plot(ax=ax2, color="#27ae60", alpha=0.4, label="Residential")

    gdf_proj[gdf_proj["building"].isin(res_types)].plot(

        ax=ax2, color="#95a5a6", alpha=0.3, label="Other")

    ax2.set_title("Residential vs Non-Residential Buildings", fontsize=12)

    ax2.legend()

    

    plt.tight_layout()

    out_png = os.path.join(BDIR, "nanshan_buildings_preview.png")

    fig.savefig(out_png, dpi=150, bbox_inches="tight")

    print(f"✓ 保存: {out_png}")

    

    # ── 与合成小区叠加 ──

    from scipy.spatial import cKDTree

    

    conn = __import__('sqlite3').connect(f"{BASE}\\village_data\\villages.db")

    villages = pd.read_sql("SELECT * FROM sz_village", conn)

    conn.close()

    

    v_coords = np.array(list(zip(villages["lng"], villages["lat"])))
    
    # 居住建筑质心

    res_centroids = np.array([(g.centroid.x, g.centroid.y) 

                               for g in res_bldg.geometry])

    

    if len(res_centroids) > 0:

        tree = cKDTree(res_centroids)

        dists, idxs = tree.query(v_coords)

        

        nearest_area = np.array([

            res_bldg.iloc[idx]["area_m2"] if idx < len(res_bldg) else np.nan

            for idx in idxs

        ])

        nearest_btype = np.array([

            res_bldg.iloc[idx]["building"] if idx < len(res_bldg) else "none"

            for idx in idxs

        ])

        

        villages["res_building_area_m2"] = nearest_area

        villages["res_building_type"]     = nearest_btype

        villages["res_building_dist_deg"] = dists

        

        match_100m = (dists < 0.001).sum()

        match_200m = (dists < 0.002).sum()

        print(f"\n合成小区 vs 居住建筑叠加:")

        print(f"  100m 内匹配: {match_100m:,} ({100*match_100m/len(villages):.1f}%)")

        print(f"  200m 内匹配: {match_200m:,} ({100*match_200m/len(villages):.1f}%)")

        

        out_v = os.path.join(OUT, "nanshan_villages_with_building.csv")

        villages.to_csv(out_v, index=False, encoding="utf-8")

        print(f"✓ 保存: {out_v}")

