# -*- coding: utf-8 -*-
import pandas as pd, sys, numpy as np
from scipy.spatial import cKDTree
sys.stdout.reconfigure(encoding='utf-8')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
GAODE_CSV = BASE + r"\osm_data\nanshan_poi_gaode.csv"
V5_CSV = BASE + r"\osm_data\nanshan_poi_v5.csv"

gaode = pd.read_csv(GAODE_CSV)
v5 = pd.read_csv(V5_CSV)

# gaode columns: lon, lat -> gcj_lon, gcj_lat
# v5 columns: lng, lat -> gcj_lon, lat (keep as-is)
gaode.rename(columns={"lon": "gcj_lon", "lat": "gcj_lat"}, inplace=True)
v5.rename(columns={"lng": "gcj_lon"}, inplace=True)

# round for matching
gaode["_lon"] = gaode["gcj_lon"].round(6)
gaode["_lat"] = gaode["gcj_lat"].round(6)
v5["_lon"] = v5["gcj_lon"].round(6)
v5["_lat"] = v5["lat"].round(6)

print(f"Gaode: {len(gaode)}, V5: {len(v5)}")

# spatial match with KDTree
v5_valid = v5.dropna(subset=["_lon", "_lat"])
gaode_valid = gaode.dropna(subset=["_lon", "_lat"])

gaode_pts = gaode_valid[["_lon", "_lat"]].values
tree = cKDTree(gaode_pts)
v5_pts = v5_valid[["_lon", "_lat"]].values
distances, indices = tree.query(v5_pts)

print(f"\nV5 points matched to Gaode by distance:")
print(f"  Exact (d=0): {np.sum(distances == 0)}/{len(v5_pts)}")
for thresh in [0.00001, 0.0001, 0.0005, 0.001, 0.005, 0.01]:
    n = np.sum(distances <= thresh)
    print(f"  d<={thresh:.5f}: {n} ({n/len(v5_pts)*100:.1f}%)")
print(f"  mean dist: {np.mean(distances):.6f}")
print(f"  median dist: {np.median(distances):.6f}")
