# -*- coding: utf-8 -*-
import pandas as pd, numpy as np, geopandas as gpd, sys, io, ast, os
from scipy.spatial import cKDTree
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# Load villages
conn = __import__('sqlite3').connect(BASE + "\\village_data\\villages.db")
villages = pd.read_sql("SELECT * FROM sz_village", conn)
conn.close()

print("villages.db 统计:")
print("  Total: {} records".format(len(villages)))
print("  lng range: {:.4f} ~ {:.4f}".format(
    float(villages["lng"].min()), float(villages["lng"].max())))
print("  lat range: {:.4f} ~ {:.4f}".format(
    float(villages["lat"].min()), float(villages["lat"].max())))

# Nanshan bbox (south, north, west, east)
NS_S = 22.45; NS_N = 22.55; NS_W = 113.85; NS_E = 114.05

# Filter to Nanshan
in_ns = villages[
    (villages["lng"] >= NS_W) & (villages["lng"] <= NS_E) &
    (villages["lat"] >= NS_S) & (villages["lat"] <= NS_N)
].copy()
print("\n南山区内小区: {} / {}".format(len(in_ns), len(villages)))
if len(in_ns) > 0:
    print("  lng: {:.4f} ~ {:.4f}".format(
        float(in_ns["lng"].min()), float(in_ns["lng"].max())))
    print("  lat: {:.4f} ~ {:.4f}".format(
        float(in_ns["lat"].min()), float(in_ns["lat"].max())))

# Load OSM buildings
bldg_path = BASE + "\\building_data\\nanshan_buildings_v2.geojson"
if os.path.exists(bldg_path):
    bldg = gpd.read_file(bldg_path)
    print("\nOSM 建筑: {:,} 个".format(len(bldg)))
    bounds = bldg.total_bounds
    print("  lon: {:.4f} ~ {:.4f}".format(bounds[0], bounds[2]))
    print("  lat: {:.4f} ~ {:.4f}".format(bounds[1], bounds[3]))
    
    # Building centroids
    bldg_4326 = bldg.to_crs("EPSG:4326")
    b_centroids = np.array([(g.x, g.y) for g in bldg_4326.geometry.centroid])
    
    if len(in_ns) > 0:
        v_coords = np.array(list(zip(in_ns["lng"].values, in_ns["lat"].values)))
        tree = cKDTree(b_centroids)
        dists, idxs = tree.query(v_coords)
        
        print("\n匹配结果 (南山区 {:,} 个小区):".format(len(in_ns)))
        for thresh_deg in [0.0005, 0.001, 0.002, 0.005, 0.01]:
            m = (dists < thresh_deg).sum()
            print("  <{:.0f}m: {} ({:.1f}%)".format(
                thresh_deg*111000, m, 100*m/len(in_ns)))
        
        # Assign nearest building data
        in_ns["res_building_dist_deg"] = dists
        in_ns["res_building_dist_m"]  = dists * 111000
        
        area_list = []
        btype_list = []
        for idx in idxs:
            if idx < len(bldg):
                area_list.append(float(bldg.iloc[idx]["area_m2"]))
                btype_list.append(str(bldg.iloc[idx]["building"]))
            else:
                area_list.append(float("nan"))
                btype_list.append("none")
        in_ns["res_building_area_m2"] = area_list
        in_ns["res_building_type"]    = btype_list
        
        # Save
        out_v = BASE + "\\osm_data\\nanshan_villages_with_building.csv"
        in_ns.to_csv(out_v, index=False, encoding="utf-8")
        print("\nSaved: " + out_v)
        
        # Stats
        matched_200m = in_ns[in_ns["res_building_dist_m"] < 200]
        print("\n南山区小区 vs 居住建筑:")
        print("  Total: {}".format(len(in_ns)))
        print("  200m matched: {} ({:.1f}%)".format(
            len(matched_200m), 100*len(matched_200m)/len(in_ns)))
        print("  Median dist: {:.0f}m".format(
            float(in_ns["res_building_dist_m"].median())))
        
        # Building type summary
        print("\n匹配的建筑类型:")
        print(in_ns["res_building_type"].value_counts().head(8).to_string())
else:
    print("\nNo building data found at: " + bldg_path)
