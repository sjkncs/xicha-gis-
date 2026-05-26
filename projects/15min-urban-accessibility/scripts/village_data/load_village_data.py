# -*- coding: utf-8 -*-
"""小区数据加载 from fang_2017-08-02.sql | 2026-05-20 """

import geopandas as gpd
import pandas as pd
import sqlite3
import os
from shapely.geometry import Point

GEOJSON = r"e:\\xicha gis 智能定位\\15分钟城市时间贫困研究\\village_data\\sz_village.geojson"
CSV = r"e:\\xicha gis 智能定位\\15分钟城市时间贫困研究\\village_data\\sz_village_geocoded.csv"
DB = r"e:\\xicha gis 智能定位\\15分钟城市时间贫困研究\\village_data\\villages.db"

def load_gdf():
    """从 GeoJSON 加载（有坐标时推荐）"""
    if not os.path.exists(GEOJSON):
        print("[INFO] GeoJSON not found:", GEOJSON)
        return None
    gdf = gpd.read_file(GEOJSON)
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)
    print("Loaded: " + str(len(gdf)) + " villages")
    return gdf

def load_df():
    """从 CSV 加载（无几何）"""
    if not os.path.exists(CSV):
        print("[INFO] CSV not found:", CSV)
        return None
    df = pd.read_csv(CSV, encoding="utf-8-sig")
    print("Loaded: " + str(len(df)) + " rows (" + str(df["lng"].notna().sum()) + " with coords)")
    return df

def load_db_gdf():
    """从 SQLite 加载 GeoDataFrame（无坐标时使用）"""
    if not os.path.exists(DB):
        print("[INFO] DB not found:", DB)
        return None
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query("SELECT * FROM sz_village", conn)
    conn.close()
    df_geo = df.dropna(subset=["lng", "lat"])
    if len(df_geo) > 0:
        gdf = gpd.GeoDataFrame(df_geo,
            geometry=[Point(xy) for xy in zip(df_geo["lng"], df_geo["lat"])],
            crs="EPSG:4326")
    else:
        gdf = gpd.GeoDataFrame(df, crs="EPSG:4326")
    print("Loaded: " + str(len(gdf)) + " from DB")
    return gdf

if __name__ == "__main__":
    gdf = load_db_gdf()
    if gdf is not None:
        print("\nDistrict distribution:")
        print(gdf["quxian"].value_counts() if "quxian" in gdf.columns else gdf["district"].value_counts())