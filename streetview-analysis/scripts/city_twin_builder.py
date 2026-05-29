# -*- coding: utf-8 -*-
"""
==============================================================================
南山区精细粒度城市数字孪生构建器
Nanshan District Fine-Grained City Digital Twin Builder

整合所有数据层：建筑底座 + OSM路网 + 连续轨迹 + 语义分割可达性
生成单一 GeoJSON + CesiumJS/Leaflet 交互式可视化

用法:
    python city_twin_builder.py --mode preview

    python city_twin_builder.py --mode full
        --trajectory trajectory_output/trajectory_preview_20m.csv.csv
        --buildings "..\\projects\\15min-urban-accessibility\\building_data\\nanshan_buildings_official.geojson"
        --roads "..\\projects\\15min-urban-accessibility\\osm_data\\nanshan_road_network.shp"
        --metrics "gpu_scripts\\per_location_metrics.csv"
        --output city_digital_twin.geojson

依赖:
    pip install numpy pandas shapely geopandas scipy
==============================================================================
"""

import os
import sys
import json
import math
import csv
import logging
import argparse
import shutil
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiLineString
from shapely.ops import unary_union, transform as shapely_transform
from scipy.spatial import cKDTree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# 路径配置
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT_DIR = SCRIPT_DIR.parent
PROJ_DIR = ROOT_DIR / "projects" / "15min-urban-accessibility"
DATA_DIR = PROJ_DIR / "building_data"
OSM_DIR = PROJ_DIR / "osm_data"
OUT_DIR = SCRIPT_DIR / "city_twin_output"
OUT_DIR.mkdir(exist_ok=True)

# 建筑用途类型 → 颜色
USE_TYPE_COLORS = {
    1: (120, 180, 220, 200, "住宅"),
    2: (255, 200, 80,  200, "商业"),
    3: (200, 100, 220, 200, "办公"),
    4: (180, 100, 80,  200, "工业"),
    5: (80,  160, 100, 200, "文体"),
    6: (220, 80,  80,  200, "医疗"),
    7: (220, 150, 60,  200, "文化"),
    8: (100, 200, 220, 200, "科教"),
    9: (180, 180, 180, 200, "其他"),
}

# 南山区边界近似
NANSHAN_BOUNDS = {
    "min_lon": 113.8210,
    "max_lon": 114.0938,
    "min_lat": 22.4670,
    "max_lat": 22.6736,
}

FLOOR_HEIGHT_M = 3.0


# ============================================================
# 工具函数
# ============================================================

def haversine_m(lon1, lat1, lon2, lat2):
    """计算两点间大圆距离（米）"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def meters_per_degree(lat):
    """估算某纬度1度对应的米数（经度×cos(lat)，纬度）"""
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * math.radians(lat)) + 1.175 * math.cos(4 * math.radians(lat))
    m_per_deg_lon = 111412.84 * math.cos(math.radians(lat)) - 93.5 * math.cos(3 * math.radians(lat))
    return m_per_deg_lat, abs(m_per_deg_lon)


def dynamic_buffer_radius(floors):
    """根据楼层数动态计算缓冲半径（米）"""
    if floors >= 40:
        return 50
    elif floors >= 25:
        return 40
    elif floors >= 15:
        return 32
    elif floors >= 8:
        return 24
    elif floors >= 4:
        return 18
    else:
        return 12


def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"


def walkability_color(score):
    """可达性评分 → 颜色（红→黄→绿）"""
    if score is None or math.isnan(score):
        return "#484f58"
    score = max(0, min(10, float(score)))
    t = score / 10.0
    if t < 0.4:
        r = 255
        g = int(120 + 135 * t / 0.4)
        b = 80
    elif t < 0.7:
        r = int(255 - 255 * (t - 0.4) / 0.3)
        g = int(255 - 135 * (t - 0.4) / 0.3)
        b = 80
    else:
        r = int(255 * (1 - t) / 0.3)
        g = 255
        b = int(80 + 175 * (t - 0.7) / 0.3)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_walkability_score(w):
    """从百分数计算综合可达性评分 (0-10)"""
    if w is None or math.isnan(w):
        return None
    return float(w) / 10.0


def in_nanshan(lon, lat):
    return (NANSHAN_BOUNDS["min_lon"] <= lon <= NANSHAN_BOUNDS["max_lon"]
            and NANSHAN_BOUNDS["min_lat"] <= lat <= NANSHAN_BOUNDS["max_lat"])


# ============================================================
# Step 1: 加载建筑数据
# ============================================================
def load_buildings(geojson_path=None):
    """加载官方建筑楼栋点数据，转换为带属性的 GeoDataFrame"""
    if geojson_path is None:
        geojson_path = DATA_DIR / "nanshan_buildings_official.geojson"

    if not Path(geojson_path).exists():
        log.warning(f"  建筑文件不存在: {geojson_path}，跳过")
        return None

    log.info(f"Step 1: 加载建筑楼栋数据...")
    gdf = gpd.read_file(geojson_path)
    log.info(f"  加载楼栋: {len(gdf):,} 个")
    log.info(f"  CRS: {gdf.crs}")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    gdf["floors"] = pd.to_numeric(gdf.get("floors", 1), errors="coerce").fillna(1).clip(1, 100)
    gdf["height_m"] = gdf["floors"] * FLOOR_HEIGHT_M
    gdf["use_type"] = pd.to_numeric(gdf.get("use_type", 9), errors="coerce").fillna(9).astype(int)
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y

    gdf["use_name"] = gdf["use_type"].map(
        lambda x: USE_TYPE_COLORS.get(x, (180, 180, 180, 200, "未知"))[4]
    )

    colors = []
    for ut in gdf["use_type"]:
        c = USE_TYPE_COLORS.get(ut, (180, 180, 180, 200, "未知"))
        colors.append({"r": c[0], "g": c[1], "b": c[2]})
    gdf["color"] = colors

    return gdf


# ============================================================
# Step 2: 建筑点 → 面（动态缓冲）
# ============================================================
def buildings_to_polygons(buildings_gdf, base_buffer_m=30):
    """将楼栋点转为建筑面，根据楼层动态设置缓冲半径"""
    if buildings_gdf is None:
        return None

    log.info(f"Step 2: 建筑点转面 (动态缓冲)...")
    gdf = buildings_gdf.copy()

    def dynamic_buffer(row):
        floors = row["floors"]
        r = dynamic_buffer_radius(floors)
        lat = row["lat"]
        m_per_deg_lat, m_per_deg_lon = meters_per_degree(lat)
        buffer_deg = r / m_per_deg_lat
        return row.geometry.buffer(buffer_deg, cap_style=1)

    gdf.geometry = gdf.apply(dynamic_buffer, axis=1)

    valid = gdf[gdf.geometry.is_valid]
    invalid = len(gdf) - len(valid)
    if invalid > 0:
        log.warning(f"  修复 {invalid} 个无效几何")
        gdf.loc[~gdf.geometry.is_valid, "geometry"] = (
            gdf.loc[~gdf.geometry.is_valid].geometry.buffer(0)
        )

    log.info(f"  生成 {len(gdf):,} 个建筑面")
    return gdf


# ============================================================
# Step 3: 加载 OSM 路网（SHP 格式）
# ============================================================
def load_road_network(shp_path=None):
    """从 SHP 线数据加载路网"""
    if shp_path is None:
        shp_path = OSM_DIR / "nanshan_road_network.shp"

    if not Path(shp_path).exists():
        log.warning(f"  路网 SHP 不存在: {shp_path}，跳过")
        return None

    log.info(f"Step 3: 加载 OSM 路网...")
    gdf = gpd.read_file(shp_path)
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    def extract_line(g):
        geom_type = g.geom_type
        if geom_type == "LineString":
            return g
        elif geom_type == "MultiLineString":
            parts = list(g.geoms)
            if len(parts) == 1:
                return parts[0]
            lines = [p for p in parts if p.is_valid and not p.is_empty]
            return MultiLineString(lines) if lines else None
        elif geom_type == "GeometryCollection":
            parts = [extract_line(p) for p in getattr(g, "geoms", [])]
            parts = [p for p in parts if p is not None and p.is_valid and not p.is_empty]
            if not parts:
                return None
            if len(parts) == 1:
                return parts[0]
            return MultiLineString(parts)
        elif geom_type == "MultiPolygon":
            return None
        elif geom_type == "Polygon":
            return None
        elif geom_type == "Point":
            return None
        return None

    rows = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or not geom.is_valid:
            continue
        line = extract_line(geom)
        if line is None:
            continue
        rows.append({
            "geometry": line,
            "fclass": str(row.get("highway", row.get("fclass", "unknown"))),
            "name": str(row.get("name", row.get("ref", ""))),
        })

    if not rows:
        log.warning("  路网几何提取失败")
        return None

    result = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    log.info(f"  加载路网: {len(result):,} 条线段")

    # 统计
    fclass_counts = result["fclass"].value_counts().head(8)
    for fc, cnt in fclass_counts.items():
        log.info(f"    {fc}: {cnt:,}")

    return result


# ============================================================
# Step 4: 加载连续轨迹点
# ============================================================
def load_trajectory(trajectory_csv_path, spacing=20):
    """加载轨迹采样器生成的轨迹点"""
    if trajectory_csv_path is None:
        return None

    csv_path = Path(trajectory_csv_path)
    if not csv_path.exists():
        log.warning(f"  轨迹文件不存在: {csv_path}，跳过")
        return None

    log.info(f"Step 4: 加载连续轨迹点...")
    df = pd.read_csv(csv_path)

    # 清理列名
    df.columns = [c.strip() for c in df.columns]
    col_map = {}
    for c in df.columns:
        cl = c.lower()
        if "lon" in cl or "x" == cl:
            col_map[c] = "lon"
        elif "lat" in cl or "y" == cl:
            col_map[c] = "lat"
        elif "floors" in cl:
            col_map[c] = "floors"
        elif "density" in cl:
            col_map[c] = "building_density"
        elif "urban" in cl and "form" in cl:
            col_map[c] = "urban_form"
        elif "heading" in cl and "label" not in cl:
            col_map[c] = "heading"
        elif "fclass" in cl or "road" in cl:
            col_map[c] = "fclass"

    df = df.rename(columns=col_map)
    if "lon" not in df.columns or "lat" not in df.columns:
        log.warning(f"  轨迹 CSV 缺少 lon/lat 列: {list(df.columns)}")
        return None

    # 过滤南山区
    df = df[df.apply(lambda r: in_nanshan(r["lon"], r["lat"]), axis=1)].copy()
    log.info(f"  加载轨迹点: {len(df):,} 个 (spacing={spacing}m)")

    # 构建 KDTree 用于后续查询
    coords = df[["lon", "lat"]].values
    tree = cKDTree(coords)

    return df, tree


# ============================================================
# Step 5: 加载语义分割可达性指标
# ============================================================
def load_segmentation_metrics(metrics_path_str=None):
    """加载每位置可达性指标，构建 KDTree"""
    if metrics_path_str is None:
        candidates = [
            SCRIPT_DIR / "gpu_scripts" / "per_location_metrics.csv",
            SCRIPT_DIR / "baidu_streetview" / "segmentation_results_v3" / "seg_final_clean.csv",
        ]
        found = next((p for p in candidates if p.exists()), None)
        metrics_path_str = str(found) if found else None

    if metrics_path_str is None or not Path(metrics_path_str).exists():
        log.warning("  语义分割指标文件不存在，跳过可达性着色")
        return None

    log.info(f"Step 5: 加载语义分割指标: {Path(metrics_path_str).name}...")
    df = pd.read_csv(metrics_path_str)
    df.columns = [c.strip() for c in df.columns]

    log.info(f"  加载指标点: {len(df):,} 个")

    # 解析 lat_lon 列
    if "lat_lon" in df.columns:
        lon_list, lat_list = [], []
        for v in df["lat_lon"]:
            parts = str(v).split("_")
            if len(parts) >= 2:
                try:
                    lon_list.append(float(parts[0]))
                    lat_list.append(float(parts[1]))
                except ValueError:
                    lon_list.append(None)
                    lat_list.append(None)
            else:
                lon_list.append(None)
                lat_list.append(None)
        df["lon"] = lon_list
        df["lat"] = lat_list

    # 计算综合可达性评分
    if "pct_building" in df.columns:
        df["walkability"] = df["pct_building"] / 10.0

    # 构建 KDTree（只保留有坐标的行）
    if "lon" not in df.columns or "lat" not in df.columns:
        log.warning("  缺少 lon/lat 列")
        return None

    valid_mask = df.apply(lambda r: not pd.isna(r.get("lon")) and not pd.isna(r.get("lat")), axis=1)
    valid_data = df[valid_mask].copy()
    log.info(f"  有效坐标点: {len(valid_data):,} 个")

    if len(valid_data) == 0:
        return None

    coords = valid_data[["lon", "lat"]].values.astype(float)
    tree = cKDTree(coords)
    seg_data = valid_data.reset_index(drop=True)
    seg_data = valid_data.reset_index(drop=True)

    log.info(f"  构建可达性 KDTree: {len(seg_data):,} 个有效点")
    return seg_data, tree


def nearest_segmentation(lon, lat, seg_tree, seg_data, max_dist_m=500):
    """查找最近可达性指标点"""
    if seg_tree is None:
        return None
    dist, idx = seg_tree.query([lon, lat], k=1)
    if dist > max_dist_m / 111000.0:
        return None
    row = seg_data.iloc[idx]
    return float(row.get("walkability", 0)) if not pd.isna(row.get("walkability")) else None


# ============================================================
# Step 6: 加载已有街景全景点（manifest）
# ============================================================
def load_panorama_points():
    """从 manifest 加载已有街景采集点"""
    manifest_paths = [
        SCRIPT_DIR / "baidu_streetview" / "ns_manifest.csv",
        SCRIPT_DIR / "baidu_streetview" / "manifest.csv",
    ]
    for mp in manifest_paths:
        if mp.exists():
            break
    else:
        return None

    log.info(f"Step 6: 加载已有全景点: {mp.name}...")
    rows = []
    with open(mp, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lng = float(row.get("lng", 0))
                lat = float(row.get("lat", 0))
                if not in_nanshan(lng, lat):
                    continue
                rows.append({
                    "geometry": Point(lng, lat),
                    "lng": lng,
                    "lat": lat,
                    "heading": row.get("heading_label", ""),
                    "district": row.get("district", ""),
                    "township": row.get("township", ""),
                    "road_name": row.get("road_name", ""),
                    "urban_form": row.get("urban_form", ""),
                    "year": row.get("year", ""),
                })
            except (ValueError, KeyError):
                continue

    if not rows:
        return None

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    log.info(f"  已有全景点: {len(gdf):,} 个")
    return gdf


# ============================================================
# Step 6b: 加载设施 POI（支持"15分钟生活圈"可视化）
# ============================================================
FACILITY_KEYWORDS = {
    "school": ["学校", "幼儿园", "小学", "中学"],
    "hospital": ["医院", "诊所", "卫生站", "社康"],
    "park": ["公园", "绿化", "广场", "绿地"],
    "market": ["市场", "超市", "菜市场", "农贸市场"],
    "metro": ["地铁", "地铁站"],
    "bus": ["公交站", "公交"],
}

FACILITY_COLORS = {
    "school": "#4CAF50",
    "hospital": "#F44336",
    "park": "#8BC34A",
    "market": "#FF9800",
    "metro": "#3F51B5",
    "bus": "#9C27B0",
}

FACILITY_NAMES = {
    "school": "学校",
    "hospital": "医疗",
    "park": "公园绿化",
    "market": "菜市场",
    "metro": "地铁站",
    "bus": "公交站",
}

def classify_poi(name, cat1, cat2):
    name_cat = f"{name}{cat1}{cat2}"
    for ftype, keywords in FACILITY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_cat:
                return ftype
    return None


def load_poi(poi_csv_path):
    """从 POI CSV 加载南山区设施点，分类后返回 GeoDataFrame"""
    import csv as csvlib
    if not Path(poi_csv_path).exists():
        log.warning(f"  POI 文件不存在: {poi_csv_path}，跳过设施图层")
        return None

    # 判断列名（lon/lat vs lng/lat）
    with open(poi_csv_path, encoding="utf-8") as f:
        sample = f.read(500)
    has_lon = "lon" in sample
    has_lng = "lng" in sample
    lon_col = "lon" if has_lon else ("lng" if has_lng else None)
    lat_col = "lat" if "lat" in sample else None
    if not lon_col or not lat_col:
        log.warning(f"  POI 文件缺少坐标列，跳过")
        return None

    rows = []
    with open(poi_csv_path, encoding="utf-8") as f:
        reader = csvlib.DictReader(f)
        for row in reader:
            try:
                lon = float(row[lon_col])
                lat = float(row[lat_col])
                name = str(row.get("name", ""))
                cat1 = str(row.get("category1", ""))
                cat2 = str(row.get("category2", ""))
                ftype = classify_poi(name, cat1, cat2)
                if ftype is None:
                    continue
            except (ValueError, KeyError):
                continue

            if not in_nanshan(lon, lat):
                continue

            rows.append({
                "geometry": Point(lon, lat),
                "name": name,
                "category1": cat1,
                "category2": cat2,
                "facility_type": ftype,
            })

    if not rows:
        return None

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    log.info(f"  设施 POI: {len(gdf):,} 个")
    for ftype, count in gdf["facility_type"].value_counts().items():
        log.info(f"    {FACILITY_NAMES.get(ftype, ftype)}: {count}")
    return gdf


# ============================================================
# Step 7: 构建数字孪生 GeoJSON
# ============================================================
def build_digital_twin(
    buildings_gdf,
    road_network_gdf,
    trajectory_df,
    seg_data,
    seg_tree,
    panorama_gdf,
    poi_gdf,
    output_path,
    mode="standard",
):
    """整合所有数据层，输出 GeoJSON FeatureCollection"""
    log.info(f"\n{'=' * 60}")
    log.info(f"构建南山区精细粒度数字孪生 GeoJSON (mode={mode})")
    log.info(f"{'=' * 60}")

    features = []

    # --- 道路层 ---
    if road_network_gdf is not None:
        log.info(f"添加路网层: {len(road_network_gdf):,} 条")
        for _, row in road_network_gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            props = {
                "layer": "road",
                "fclass": row.get("fclass", "unknown"),
                "name": row.get("name", ""),
            }
            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geom.__geo_interface__,
            })

    # --- 建筑层 ---
    if buildings_gdf is not None:
        log.info(f"添加建筑层: {len(buildings_gdf):,} 栋")
        for _, row in buildings_gdf.iterrows():
            geom = row.geometry
            if geom is None or not geom.is_valid:
                continue

            props = {
                "layer": "building",
                "floors": int(row.get("floors", 1)),
                "height_m": float(row.get("height_m", 3)),
                "use_type": int(row.get("use_type", 9)),
                "use_name": str(row.get("use_name", "其他")),
                "lon": float(row.get("lon", 0)),
                "lat": float(row.get("lat", 0)),
                "walkability": None,
                "walkability_color": "#484f58",
                "building_color": rgb_to_hex(
                    row.get("color", {}).get("r", 180),
                    row.get("color", {}).get("g", 180),
                    row.get("color", {}).get("b", 180),
                ),
            }

            # 关联可达性
            if seg_tree is not None and seg_data is not None:
                ws = nearest_segmentation(row["lon"], row["lat"], seg_tree, seg_data, max_dist_m=200)
                props["walkability"] = ws
                props["walkability_color"] = walkability_color(ws * 10 if ws is not None else None)

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": geom.__geo_interface__,
            })

    # --- 连续轨迹层 ---
    if trajectory_df is not None:
        tdf = trajectory_df[0] if isinstance(trajectory_df, tuple) else trajectory_df
        log.info(f"添加连续轨迹层: {len(tdf):,} 个采样点")
        for _, row in tdf.iterrows():
            try:
                lon = float(row["lon"])
                lat = float(row["lat"])
            except (KeyError, ValueError):
                continue

            if not in_nanshan(lon, lat):
                continue

            props = {
                "layer": "trajectory",
                "pt_id": int(row.get("pt_id", 0)),
                "fclass": str(row.get("fclass", "")),
                "building_density": str(row.get("building_density", "")),
                "urban_form": str(row.get("urban_form", "")),
                "heading": float(row.get("heading", 0)) if not pd.isna(row.get("heading")) else 0,
                "heading_label": str(row.get("heading_label", "")),
                "dist_from_start_m": float(row.get("dist_from_start_m", 0)) if not pd.isna(row.get("dist_from_start_m", 0)) else 0,
            }

            # 关联可达性
            if seg_tree is not None and seg_data is not None:
                ws = nearest_segmentation(lon, lat, seg_tree, seg_data, max_dist_m=300)
                props["walkability"] = ws
                props["walkability_color"] = walkability_color(ws * 10 if ws is not None else None)

            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            })

    # --- 全景点层 ---
    if panorama_gdf is not None:
        log.info(f"添加全景点层: {len(panorama_gdf):,} 个")
        for _, row in panorama_gdf.iterrows():
            props = {
                "layer": "panorama",
                "lng": float(row.get("lng", 0)),
                "lat": float(row.get("lat", 0)),
                "heading": str(row.get("heading", "")),
                "district": str(row.get("district", "")),
                "township": str(row.get("township", "")),
                "road_name": str(row.get("road_name", "")),
                "urban_form": str(row.get("urban_form", "")),
                "year": str(row.get("year", "")),
            }
            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": row.geometry.__geo_interface__,
            })

    # --- 设施 POI 层 ---
    if poi_gdf is not None:
        log.info(f"添加设施 POI 层: {len(poi_gdf):,} 个")
        for _, row in poi_gdf.iterrows():
            props = {
                "layer": "poi",
                "name": str(row.get("name", "")),
                "category1": str(row.get("category1", "")),
                "category2": str(row.get("category2", "")),
                "facility_type": str(row.get("facility_type", "")),
            }
            features.append({
                "type": "Feature",
                "properties": props,
                "geometry": row.geometry.__geo_interface__,
            })

    fc = {"type": "FeatureCollection", "features": features}
    log.info(f"\nGeoJSON 统计:")
    log.info(f"  总 Feature 数: {len(features):,}")
    log.info(f"  路网: {sum(1 for f in features if f['properties']['layer'] == 'road'):,}")
    log.info(f"  建筑: {sum(1 for f in features if f['properties']['layer'] == 'building'):,}")
    log.info(f"  轨迹: {sum(1 for f in features if f['properties']['layer'] == 'trajectory'):,}")
    log.info(f"  全景: {sum(1 for f in features if f['properties']['layer'] == 'panorama'):,}")
    log.info(f"  设施: {sum(1 for f in features if f['properties']['layer'] == 'poi'):,}")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(fc, f, ensure_ascii=False)
    log.info(f"  保存至: {output_path}")

    return fc


# ============================================================
# Step 8: 生成交互式 HTML 可视化器
# ============================================================
def generate_viewer(geojson_path, output_html=None):
    """生成 Leaflet/Cesium 交互式 HTML 可视化器"""
    if output_html is None:
        output_html = OUT_DIR / "city_twin_viewer.html"

    log.info(f"\n生成交互式可视化器: {output_html}")

    # 读取 GeoJSON 并内嵌（解决 file:// CORS 问题）
    with open(geojson_path, "r", encoding="utf-8") as f:
        fc = json.load(f)

    html_content = _build_viewer_html(data=fc)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 同时保留单独的 GeoJSON 文件（便于其他工具使用）
    dest_geojson = OUT_DIR / Path(geojson_path).name
    if Path(geojson_path).resolve() != dest_geojson.resolve():
        shutil.copy(geojson_path, dest_geojson)
        log.info(f"  GeoJSON 复制至: {dest_geojson}")
    else:
        log.info(f"  GeoJSON 已在输出目录: {dest_geojson}")
    log.info(f"  完成！请在浏览器打开: {output_html}")

    return output_html


def _build_viewer_html(data=None):
    """
    生成 Leaflet 交互式可视化 HTML。
    GeoJSON 数据已内嵌，直接渲染无需 fetch（解决 file:// CORS 问题）。
    """
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>南山区精细粒度数字孪生</title>

<!-- Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.4.1/dist/MarkerCluster.Default.css" />

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0d1117;
    color: #e6edf3;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

#header {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border-bottom: 1px solid #30363d;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    z-index: 1000;
}

#header h1 {
    font-size: 15px;
    font-weight: 600;
    background: linear-gradient(90deg, #58a6ff, #a371f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

#stats-bar {
    font-size: 11px;
    color: #8b949e;
    margin-left: 12px;
}

.btn-group {
    display: flex;
    gap: 4px;
    align-items: center;
}

.ctrl-btn {
    padding: 4px 10px;
    border: 1px solid #30363d;
    border-radius: 5px;
    background: transparent;
    color: #8b949e;
    font-size: 11px;
    cursor: pointer;
    transition: all 0.2s;
    font-family: inherit;
}
.ctrl-btn:hover { border-color: #58a6ff; color: #58a6ff; }
.ctrl-btn.active { background: #1f6feb; border-color: #1f6feb; color: white; }

#main {
    display: flex;
    flex: 1;
    overflow: hidden;
}

#sidebar {
    width: 260px;
    background: #161b22;
    border-right: 1px solid #30363d;
    overflow-y: auto;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
}

#map { flex: 1; z-index: 1; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }

.section {
    border-bottom: 1px solid #21262d;
    padding: 12px;
}

.section-title {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8b949e;
    margin-bottom: 8px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 6px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.15s;
}
.legend-item:hover { background: #21262d; }
.legend-item.disabled { opacity: 0.4; }
.legend-color {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    flex-shrink: 0;
}
.legend-color.walkability {
    width: 40px;
    height: 8px;
    border-radius: 4px;
}

.walkability-scale {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #8b949e;
    margin-top: 4px;
}

.bar-bg {
    height: 5px;
    background: linear-gradient(to right, #c44, #cc0, #4c4);
    border-radius: 3px;
    margin-top: 4px;
}

.info-card {
    background: #1c2128;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 10px;
}
.info-row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #8b949e;
    margin-bottom: 4px;
}
.info-row span { color: #e6edf3; }

.stat-badge {
    display: inline-block;
    padding: 2px 8px;
    background: #21262d;
    border-radius: 10px;
    font-size: 11px;
    color: #8b949e;
    margin-right: 4px;
}

#loading {
    position: fixed;
    inset: 0;
    background: #0d1117;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    gap: 16px;
}
#loading.hidden { display: none; }
.spinner {
    width: 36px;
    height: 36px;
    border: 3px solid #30363d;
    border-top-color: #58a6ff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
#loading p { font-size: 14px; color: #8b949e; }

.layer-indicator {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    background: #21262d;
    color: #58a6ff;
    margin-left: 6px;
}

.toggle-switch {
    position: relative;
    width: 32px;
    height: 16px;
    flex-shrink: 0;
}
.toggle-switch input { opacity: 0; width: 0; height: 0; }
.toggle-slider {
    position: absolute;
    inset: 0;
    background: #30363d;
    border-radius: 8px;
    cursor: pointer;
    transition: 0.2s;
}
.toggle-slider:before {
    content: '';
    position: absolute;
    width: 12px;
    height: 12px;
    left: 2px;
    bottom: 2px;
    background: white;
    border-radius: 50%;
    transition: 0.2s;
}
.toggle-switch input:checked + .toggle-slider { background: #1f6feb; }
.toggle-switch input:checked + .toggle-slider:before { transform: translateX(16px); }

.layer-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 0;
    font-size: 12px;
}
.layer-row .layer-name { display: flex; align-items: center; gap: 6px; }
</style>
</head>
<body>

<div id="loading">
    <div class="spinner"></div>
    <p>加载城市数字孪生数据...</p>
</div>

<div id="header">
    <div style="display:flex;align-items:center;flex:1;gap:12px;">
        <h1>南山区精细粒度城市数字孪生</h1>
        <span id="stats-bar">初始化中...</span>
        <div style="display:flex;align-items:center;gap:6px;margin-left:auto;">
            <input type="text" id="addr-search" placeholder="输入地址搜索..." style="background:#21262d;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;font-size:12px;width:160px;">
            <button id="addr-search-btn" style="background:#1f6feb;color:white;border:none;padding:4px 10px;border-radius:4px;font-size:12px;cursor:pointer;">搜索</button>
            <span id="addr-status" style="font-size:11px;color:#8b949e;display:none;"></span>
        </div>
    </div>
    <div class="btn-group">
        <button class="ctrl-btn active" data-base="satellite">卫星</button>
        <button class="ctrl-btn" data-base="dark">深色</button>
        <button class="ctrl-btn" data-base="streets">街道</button>
    </div>
</div>

<div id="main">
    <div id="sidebar">
        <div class="section">
            <div class="section-title">数据层</div>
            <div class="layer-row">
                <span class="layer-name">🏢 建筑底座<span class="layer-indicator" id="ind-buildings">-</span></span>
                <label class="toggle-switch">
                    <input type="checkbox" id="toggle-buildings" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="layer-row">
                <span class="layer-name">🛣️ 路网</span>
                <label class="toggle-switch">
                    <input type="checkbox" id="toggle-roads" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="layer-row">
                <span class="layer-name">📍 连续轨迹<span class="layer-indicator" id="ind-trajectory">-</span></span>
                <label class="toggle-switch">
                    <input type="checkbox" id="toggle-trajectory" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="layer-row">
                <span class="layer-name">🗼 全景点<span class="layer-indicator" id="ind-panorama">-</span></span>
                <label class="toggle-switch">
                    <input type="checkbox" id="toggle-panorama" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
            <div class="layer-row">
                <span class="layer-name">🏪 设施 POI<span class="layer-indicator" id="ind-poi">-</span></span>
                <label class="toggle-switch">
                    <input type="checkbox" id="toggle-poi" checked>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        </div>

        <!-- 设施类型图例 -->
        <div class="section">
            <div class="section-title">设施类型</div>
            <div id="legend-poi"></div>
        </div>

        <div class="section">
            <div class="section-title">建筑用途类型</div>
            <div id="legend-use"></div>
        </div>

        <div class="section">
            <div class="section-title">步行可达性 (语义分割)</div>
            <div class="bar-bg"></div>
            <div class="walkability-scale">
                <span>低(0)</span>
                <span>中(5)</span>
                <span>高(10)</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">建筑信息</div>
            <div id="info-panel">
                <div style="font-size:12px;color:#8b949e;text-align:center;padding:8px;">
                    点击地图上的建筑查看详情
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">道路类型</div>
            <div id="legend-roads"></div>
        </div>

        <!-- 15分钟生活圈 -->
        <div class="section">
            <div class="section-title">🏃 我的15分钟生活圈</div>
            <div style="font-size:11px;color:#8b949e;margin-bottom:6px;">
                点击地图任意位置，查看步行可达范围
            </div>
            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;">
                <button class="ctrl-btn active" id="circle-btn-500" onclick="setWalkCircle(500)">500m</button>
                <button class="ctrl-btn" id="circle-btn-1000" onclick="setWalkCircle(1000)">1km</button>
                <button class="ctrl-btn" id="circle-btn-1500" onclick="setWalkCircle(1500)">1.5km</button>
            </div>
            <div id="circle-info" style="font-size:11px;color:#8b949e;padding:4px;background:#21262d;border-radius:4px;display:none;"></div>
            <div style="margin-top:8px;">
                <button onclick="clearWalkCircle()" style="background:#21262d;color:#e6edf3;border:1px solid #30363d;padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;width:100%;">清除</button>
            </div>
        </div>
    </div>

    <div id="map"></div>
</div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>

<script>
// ============================================================
// 地图初始化
// ============================================================
const map = L.map('map', {
    center: [22.53, 113.94],
    zoom: 14,
    zoomControl: true,
});

const baseLayers = {
    satellite: L.tileLayer(
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        { maxZoom: 19 }
    ),
    dark: L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        { maxZoom: 19 }
    ),
    streets: L.tileLayer(
        'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        { maxZoom: 19 }
    ),
};

let currentBase = 'satellite';
baseLayers.satellite.addTo(map);
L.control.scale({ imperial: false, maxWidth: 150, position: 'bottomright' }).addTo(map);

// ============================================================
// 颜色映射
// ============================================================
const USE_COLORS = {
    1: '#78b4dc', 2: '#ffc850', 3: '#c864dc',
    4: '#b46450', 5: '#50a064', 6: '#dc5050',
    7: '#dc963c', 8: '#64c8dc', 9: '#b4b4b4',
};
const USE_NAMES = {
    1: '住宅', 2: '商业', 3: '办公',
    4: '工业', 5: '文体', 6: '医疗',
    7: '文化', 8: '科教', 9: '其他',
};
const ROAD_COLORS = {
    primary: '#ff6b35',
    secondary: '#ffd23f',
    tertiary: '#3ec300',
    residential: '#7b8794',
    service: '#7b8794',
    footway: '#9999aa',
    path: '#9999aa',
    trunk: '#ff4444',
    motorway: '#ff2222',
    unclassified: '#aaaaaa',
};

function getWalkabilityColor(score) {
    if (score == null) return '#484f58';
    score = Math.max(0, Math.min(10, score));
    const t = score / 10;
    let r, g, b;
    if (t < 0.4) {
        r = 255; g = Math.round(120 + 135 * t / 0.4); b = 80;
    } else if (t < 0.7) {
        r = Math.round(255 - 255 * (t - 0.4) / 0.3);
        g = Math.round(255 - 135 * (t - 0.4) / 0.3); b = 80;
    } else {
        r = Math.round(255 * (1 - t) / 0.3);
        g = 255; b = Math.round(80 + 175 * (t - 0.7) / 0.3);
    }
    return `rgb(${r},${g},${b})`;
}

// ============================================================
// 数据层
// ============================================================
let layerBuildings, layerRoads, layerTrajectory, layerPanorama, layerPOI;
const layerToggles = {
    buildings: { el: null, layer: null, defaultOpacity: 0.65 },
    roads: { el: null, layer: null, defaultOpacity: 0.8 },
    trajectory: { el: null, layer: null, defaultOpacity: 0.9 },
    panorama: { el: null, layer: null, defaultOpacity: 1.0 },
    poi: { el: null, layer: null, defaultOpacity: 1.0 },
};

const FACILITY_COLORS_JS = {
    school: '#4CAF50',
    hospital: '#F44336',
    park: '#8BC34A',
    market: '#FF9800',
    metro: '#3F51B5',
    bus: '#9C27B0',
};
const FACILITY_NAMES_JS = {
    school: '学校',
    hospital: '医疗',
    park: '公园绿化',
    market: '菜市场',
    metro: '地铁站',
    bus: '公交站',
};

// ============================================================
// 数据层（内嵌 GeoJSON，解决 file:// CORS 问题）
// ============================================================
const DATA = """ + json.dumps(data, ensure_ascii=False) + """;

const buildings = DATA.features.filter(f => f.geometry.type === 'Polygon');
const roads = DATA.features.filter(f => f.geometry.type === 'LineString');
const trajectory = DATA.features.filter(f => f.geometry.type === 'Point' && f.properties.layer === 'trajectory');
const panorama = DATA.features.filter(f => f.geometry.type === 'Point' && f.properties.layer === 'panorama');
const poi = DATA.features.filter(f => f.geometry.type === 'Point' && f.properties.layer === 'poi');

document.getElementById('stats-bar').textContent =
    `🏢 ${buildings.length.toLocaleString()} 栋 | 🛣️ ${roads.length.toLocaleString()} 条 | 📍 轨迹 ${trajectory.length.toLocaleString()} | 🗼 全景 ${panorama.length.toLocaleString()}`;

document.getElementById('ind-buildings').textContent = buildings.length.toLocaleString();
document.getElementById('ind-trajectory').textContent = trajectory.length.toLocaleString();
document.getElementById('ind-panorama').textContent = panorama.length.toLocaleString();
document.getElementById('ind-poi').textContent = poi.length.toLocaleString();

// 建筑图例
const useTypes = [...new Set(buildings.map(f => f.properties.use_type))];
const legendDiv = document.getElementById('legend-use');
legendDiv.innerHTML = useTypes.map(ut => {
    const name = USE_NAMES[ut] || ut;
    const color = USE_COLORS[ut] || '#b4b4b4';
    return `<div class="legend-item" data-type="${ut}">
        <div class="legend-color" style="background:${color}"></div>
        <span>${name}</span>
    </div>`;
}).join('');

// 道路图例
const roadTypes = [...new Set(roads.map(f => f.properties.fclass))];
const roadLegend = document.getElementById('legend-roads');
roadLegend.innerHTML = roadTypes.map(fc => {
    const color = ROAD_COLORS[fc] || '#7b8794';
    return `<div class="legend-item">
        <div class="legend-color" style="background:${color}"></div>
        <span>${fc || 'unknown'}</span>
    </div>`;
}).join('');

// 设施 POI 图例
const poiTypes = [...new Set(poi.map(f => f.properties.facility_type))];
const poiLegend = document.getElementById('legend-poi');
poiLegend.innerHTML = poiTypes.map(ft => {
    const color = FACILITY_COLORS_JS[ft] || '#888888';
    const name = FACILITY_NAMES_JS[ft] || ft;
    return `<div class="legend-item">
        <div class="legend-color" style="background:${color}"></div>
        <span>${name} (${poi.filter(f => f.properties.facility_type === ft).length})</span>
    </div>`;
}).join('');

// 道路层
if (roads.length > 0) {
    layerRoads = L.geoJSON({ type: 'FeatureCollection', features: roads }, {
        style: feature => {
            const fc = feature.properties.fclass || '';
            const weights = { primary: 4, secondary: 3, tertiary: 2.5, trunk: 4, motorway: 4, residential: 1.5, service: 1, footway: 1, path: 1, unclassified: 1 };
            return {
                color: ROAD_COLORS[fc] || '#7b8794',
                weight: weights[fc] || 1.5,
                opacity: 0.8,
            };
        },
        onEachFeature: (f, layer) => {
            layer.bindTooltip(`🛣️ ${f.properties.fclass || 'unknown'} ${f.properties.name || ''}`, {sticky: false, className: 'leaflet-tooltip-dark'});
        }
    });
    layerToggles.roads.layer = layerRoads;
    layerRoads.addTo(map);
}

// 轨迹层
if (trajectory.length > 0) {
    layerTrajectory = L.geoJSON({ type: 'FeatureCollection', features: trajectory }, {
        pointToLayer: (f, latlng) => {
            const ws = f.properties.walkability;
            const color = ws != null ? getWalkabilityColor(ws * 10) : '#58a6ff';
            return L.circleMarker(latlng, {
                radius: 3,
                fillColor: color,
                color: color,
                weight: 0.5,
                fillOpacity: 0.85,
                opacity: 0.85,
            });
        },
        onEachFeature: (f, layer) => {
            const p = f.properties;
            const ws = p.walkability;
            const wsStr = ws != null ? `${(ws * 10).toFixed(1)}/10` : 'N/A';
            layer.bindTooltip(
                `📍 轨迹 #${p.pt_id}<br>` +
                `道路: ${p.fclass || '-'}<br>` +
                `密度: ${p.building_density || '-'}<br>` +
                `可达性: ${wsStr}`,
                {sticky: false, className: 'leaflet-tooltip-dark'}
            );
        }
    });
    layerToggles.trajectory.layer = layerTrajectory;
    layerTrajectory.addTo(map);
}

// 全景点层
if (panorama.length > 0) {
    layerPanorama = L.geoJSON({ type: 'FeatureCollection', features: panorama }, {
        pointToLayer: (f, latlng) => {
            return L.circleMarker(latlng, {
                radius: 6,
                fillColor: '#a371f7',
                color: '#8b5cf6',
                weight: 1.5,
                fillOpacity: 0.9,
            });
        },
        onEachFeature: (f, layer) => {
            const p = f.properties;
            layer.bindTooltip(
                `🗼 全景点<br>${p.township || ''} ${p.road_name || ''}<br>朝向: ${p.heading || ''} (${p.year || ''})`,
                {sticky: false, className: 'leaflet-tooltip-dark'}
            );
            layer.on('click', () => showInfoPanel('panorama', p));
        }
    });
    layerToggles.panorama.layer = layerPanorama;
    layerPanorama.addTo(map);
}

// 设施 POI 层
if (poi.length > 0) {
    layerPOI = L.geoJSON({ type: 'FeatureCollection', features: poi }, {
        pointToLayer: (f, latlng) => {
            const ft = f.properties.facility_type || '';
            const color = FACILITY_COLORS_JS[ft] || '#888888';
            return L.circleMarker(latlng, {
                radius: 5,
                fillColor: color,
                color: '#ffffff',
                weight: 1,
                fillOpacity: 0.85,
            });
        },
        onEachFeature: (f, layer) => {
            const p = f.properties;
            const ft = p.facility_type || '';
            layer.bindTooltip(
                `<b>${p.name || '设施'}</b><br>${p.category1 || ''} / ${p.category2 || ''}<br><span style="color:${FACILITY_COLORS_JS[ft] || '#888'}">${FACILITY_NAMES_JS[ft] || ft}</span>`,
                {sticky: false, className: 'leaflet-tooltip-dark'}
            );
        }
    });
    layerToggles.poi.layer = layerPOI;
    layerPOI.addTo(map);
}

// 建筑层（默认按可达性着色，可切换用途）
let colorMode = 'walkability';

layerBuildings = L.geoJSON({ type: 'FeatureCollection', features: buildings }, {
    style: feature => {
        const p = feature.properties;
        if (colorMode === 'walkability') {
            const ws = p.walkability;
            const color = ws != null ? getWalkabilityColor(ws * 10) : '#484f58';
            return { fillColor: color, color: color, weight: 0.3, fillOpacity: 0.6, opacity: 0.3 };
        } else {
            const color = USE_COLORS[p.use_type] || '#b4b4b4';
            return { fillColor: color, color: '#ffffff44', weight: 0.5, fillOpacity: 0.7, opacity: 0.5 };
        }
    },
    onEachFeature: (f, layer) => {
        const p = f.properties;
        const ws = p.walkability;
        const wsStr = ws != null ? `${(ws * 10).toFixed(1)}/10` : 'N/A';
        const color = ws != null ? getWalkabilityColor(ws * 10) : '#484f58';
            layer.bindTooltip(
                `🏢 ${p.use_name || '建筑'}<br>层数: ${p.floors || '-'} 层 (${p.height_m || '-'}m)<br>用途类型: ${p.use_type || '-'}<br>可达性: <span style="color:${color}">${wsStr}</span>`,
                {sticky: true, className: 'leaflet-tooltip-dark'}
            );
        layer.on('click', () => showInfoPanel('building', p));
    }
});
layerToggles.buildings.layer = layerBuildings;
layerBuildings.addTo(map);

// 点击图例切换着色模式
document.getElementById('legend-use').addEventListener('click', (e) => {
    const item = e.target.closest('.legend-item');
    if (!item) return;
    colorMode = 'use';
    if (layerBuildings) layerBuildings.setStyle(f => {
        const color = USE_COLORS[f.properties.use_type] || '#b4b4b4';
        return { fillColor: color, color: '#ffffff44', weight: 0.5, fillOpacity: 0.7, opacity: 0.5 };
    });
});

// 隐藏加载
document.getElementById('loading').classList.add('hidden');

// ============================================================
// 信息面板
// ============================================================
function showInfoPanel(type, p) {
    const panel = document.getElementById('info-panel');
    if (type === 'building') {
        const ws = p.walkability;
        const wsStr = ws != null ? `${(ws * 10).toFixed(1)}/10` : '无数据';
        const wsColor = ws != null ? getWalkabilityColor(ws * 10) : '#484f58';
        panel.innerHTML = `
            <div class="info-row">用途: <span>${p.use_name || '未知'}</span></div>
            <div class="info-row">层数: <span>${p.floors || '-'} 层</span></div>
            <div class="info-row">高度: <span>${p.height_m ? p.height_m.toFixed(1) + 'm' : '-'}</span></div>
            <div class="info-row">坐标: <span>${p.lon ? p.lon.toFixed(5) + ', ' + p.lat.toFixed(5) : '-'}</span></div>
            <div class="info-row">可达性: <span style="color:${wsColor}">${wsStr}</span></div>
        `;
    } else if (type === 'panorama') {
        panel.innerHTML = `
            <div class="info-row">街道: <span>${p.township || '-'}</span></div>
            <div class="info-row">道路: <span>${p.road_name || '-'}</span></div>
            <div class="info-row">朝向: <span>${p.heading || '-'}</span></div>
            <div class="info-row">年份: <span>${p.year || '-'}</span></div>
        `;
    }
}

// ============================================================
// 底图切换
// ============================================================
document.querySelectorAll('[data-base]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('[data-base]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.dataset.base;
        if (baseLayers[currentBase]) map.removeLayer(baseLayers[currentBase]);
        baseLayers[mode].addTo(map);
        currentBase = mode;
    });
});

// ============================================================
// 图层切换
// ============================================================
const toggleMap = {
    buildings: document.getElementById('toggle-buildings'),
    roads: document.getElementById('toggle-roads'),
    trajectory: document.getElementById('toggle-trajectory'),
    panorama: document.getElementById('toggle-panorama'),
    poi: document.getElementById('toggle-poi'),
};

Object.entries(toggleMap).forEach(([key, el]) => {
    if (!el) return;
    el.addEventListener('change', () => {
        const info = layerToggles[key];
        if (!info || !info.layer) return;
        if (el.checked) {
            info.layer.addTo(map);
        } else {
            map.removeLayer(info.layer);
        }
    });
});

// ============================================================
// 地址搜索（使用 Nominatim API，无需 key）
// ============================================================
let searchMarker = null;
document.getElementById('addr-search-btn').addEventListener('click', doAddressSearch);
document.getElementById('addr-search').addEventListener('keydown', e => { if (e.key === 'Enter') doAddressSearch(); });

function doAddressSearch() {
    const query = document.getElementById('addr-search').value.trim();
    if (!query) return;
    const status = document.getElementById('addr-status');
    status.textContent = '搜索中...';
    status.style.display = 'inline';
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query + ', 南山区, 深圳')}&limit=1`;
    fetch(url, { headers: { 'Accept': 'application/json' } })
        .then(r => r.json())
        .then(results => {
            if (results.length > 0) {
                const r = results[0];
                const lat = parseFloat(r.lat);
                const lon = parseFloat(r.lon);
                if (searchMarker) map.removeLayer(searchMarker);
                searchMarker = L.circleMarker([lat, lon], {
                    radius: 10, color: '#ff6b6b', fillColor: '#ff6b6b',
                    fillOpacity: 0.8, weight: 3,
                }).addTo(map).bindPopup(`<b>${r.display_name.split(',')[0]}</b><br>${r.display_name}`).openPopup();
                map.setView([lat, lon], 17);
                status.textContent = '已定位';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            } else {
                status.textContent = '未找到';
                setTimeout(() => { status.style.display = 'none'; }, 3000);
            }
        })
        .catch(() => {
            status.textContent = '搜索失败';
            setTimeout(() => { status.style.display = 'none'; }, 3000);
        });
}

// ============================================================
// 15分钟生活圈（步行可达半径圈）
// ============================================================
let walkCircleLayer = null;
let walkCircleMarker = null;
let walkCircleRadius = 500;
let clickedLatLng = null;

// 点击地图 → 画圈 + 统计圈内设施
map.on('click', e => {
    clickedLatLng = e.latlng;
    if (walkCircleLayer) map.removeLayer(walkCircleLayer);
    if (walkCircleMarker) map.removeLayer(walkCircleMarker);
    drawWalkCircle(e.latlng, walkCircleRadius);
    updateCircleInfo(e.latlng);
});

function setWalkCircle(r) {
    walkCircleRadius = r;
    document.querySelectorAll('[id^="circle-btn-"]').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('circle-btn-' + r);
    if (btn) btn.classList.add('active');
    if (clickedLatLng) {
        if (walkCircleLayer) map.removeLayer(walkCircleLayer);
        drawWalkCircle(clickedLatLng, r);
        updateCircleInfo(clickedLatLng);
    }
}

function drawWalkCircle(latlng, radius) {
    walkCircleLayer = L.circle(latlng, {
        radius: radius,
        color: '#ff6b35',
        fillColor: '#ff6b35',
        fillOpacity: 0.08,
        weight: 2,
        dashArray: '6 4',
    }).addTo(map);
    walkCircleMarker = L.circleMarker(latlng, {
        radius: 6, color: '#ff6b35', fillColor: '#ffffff', fillOpacity: 1, weight: 2,
    }).addTo(map);
}

function updateCircleInfo(latlng) {
    const infoDiv = document.getElementById('circle-info');
    if (!infoDiv) return;
    // Haversine: 1度纬度 ≈ 111km
    const toRad = d => d * Math.PI / 180;
    const R = 6371000;
    const lat1 = latlng.lat * Math.PI / 180;
    const lat2 = latlng.lat * Math.PI / 180;
    const dLat = 0;
    const dLon = (latlng.lng - latlng.lng) * Math.PI / 180;
    // 简单：直接用半径判断

    let inCount = { school: 0, hospital: 0, park: 0, market: 0, metro: 0, bus: 0 };
    poi.forEach(f => {
        const [lon, lat] = f.geometry.coordinates;
        const dLat = (lat - latlng.lat) * 111000;
        const dLon2 = (lon - latlng.lng) * 111000 * Math.cos(latlng.lat * Math.PI / 180);
        const dist = Math.sqrt(dLat * dLat + dLon2 * dLon2);
        if (dist <= walkCircleRadius) {
            const ft = f.properties.facility_type;
            if (inCount[ft] !== undefined) inCount[ft]++;
        }
    });
    const total = Object.values(inCount).reduce((a, b) => a + b, 0);
    const rows = Object.entries(inCount)
        .filter(([, v]) => v > 0)
        .map(([ft, cnt]) => `<span style="color:${FACILITY_COLORS_JS[ft]};">${FACILITY_NAMES_JS[ft] || ft}: <b>${cnt}</b>个</span>`)
        .join(' &nbsp; ');
    infoDiv.style.display = 'block';
    infoDiv.innerHTML = `<b>${(walkCircleRadius / 1000).toFixed(1)}km 步行圈内设施(${total}个)</b><br>${rows || '无分类设施'}`;
}

function clearWalkCircle() {
    if (walkCircleLayer) { map.removeLayer(walkCircleLayer); walkCircleLayer = null; }
    if (walkCircleMarker) { map.removeLayer(walkCircleMarker); walkCircleMarker = null; }
    const infoDiv = document.getElementById('circle-info');
    if (infoDiv) { infoDiv.style.display = 'none'; }
    clickedLatLng = null;
}
</script>

<style>
.leaflet-tooltip-dark {
    background: rgba(22,27,34,0.95);
    border: 1px solid #30363d;
    color: #e6edf3;
    font-size: 12px;
    border-radius: 6px;
    padding: 8px 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
}
.leaflet-tooltip-dark::before { display: none; }
</style>
</body>
</html>
"""
    return html


# ============================================================
# 主函数
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="南山区精细粒度城市数字孪生构建器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python city_twin_builder.py --mode preview
    python city_twin_builder.py --mode full
        --buildings "..\\projects\\15min-urban-accessibility\\building_data\\nanshan_buildings_official.geojson"
        --roads "..\\projects\\15min-urban-accessibility\\osm_data\\nanshan_road_network.shp"
        --trajectory trajectory_output/trajectory_preview_20m.csv.csv
        --metrics gpu_scripts/per_location_metrics.csv
        --output city_digital_twin.geojson
        """,
    )
    parser.add_argument("--mode", default="preview", choices=["preview", "full"],
                        help="preview: 快速测试(无轨迹); full: 完整生成(含连续轨迹)")
    parser.add_argument("--buildings", default=None, help="建筑 GeoJSON 路径")
    parser.add_argument("--roads", default=None, help="路网 SHP 路径")
    parser.add_argument("--trajectory", default=None, help="轨迹 CSV 路径")
    parser.add_argument("--metrics", default=None, help="语义分割指标 CSV")
    parser.add_argument("--poi", default=None, help="POI CSV 路径（自动识别设施类型）")
    parser.add_argument("--output", default="city_digital_twin.geojson", help="输出 GeoJSON 文件名")
    parser.add_argument("--no-viewer", action="store_true", help="跳过 HTML 可视化器生成")
    args = parser.parse_args()

    log.info(f"\n{'#' * 60}")
    log.info(f"# 南山区精细粒度城市数字孪生构建器")
    log.info(f"# Mode: {args.mode}")
    log.info(f"# {'#' * 60}")

    output_geojson = OUT_DIR / args.output

    # Step 1: 建筑
    buildings_gdf = load_buildings(args.buildings)
    if buildings_gdf is not None:
        buildings_gdf = buildings_to_polygons(buildings_gdf)

    # Step 3: 路网
    road_network_gdf = load_road_network(args.roads)

    # Step 4: 轨迹
    trajectory_data = None
    if args.mode == "full" and args.trajectory:
        trajectory_data = load_trajectory(args.trajectory)

    # Step 5: 语义分割
    seg_data = None
    seg_tree = None
    metrics_path_str = args.metrics if args.metrics else None
    if metrics_path_str is None:
        candidates = [
            SCRIPT_DIR / "gpu_scripts" / "per_location_metrics.csv",
            SCRIPT_DIR / "baidu_streetview" / "segmentation_results_v3" / "seg_final_clean.csv",
        ]
        for p in candidates:
            if p.exists():
                metrics_path_str = str(p)
                break
    if metrics_path_str:
        result = load_segmentation_metrics(metrics_path_str)
        if result is not None:
            seg_data, seg_tree = result

    # Step 6: 全景点
    panorama_gdf = load_panorama_points()

    # Step 6b: 设施 POI
    poi_csv_path = args.poi
    if poi_csv_path is None:
        poi_candidates = [
            SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "osm_data" / "nanshan_poi_integrated_v3_wgs84.csv",
            SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "osm_data" / "nanshan_poi_integrated_v3.csv",
        ]
        for p in poi_candidates:
            if p.exists():
                poi_csv_path = str(p)
                break
    poi_gdf = None
    if poi_csv_path:
        poi_gdf = load_poi(poi_csv_path)

    # Step 7: 构建数字孪生
    fc = build_digital_twin(
        buildings_gdf=buildings_gdf,
        road_network_gdf=road_network_gdf,
        trajectory_df=trajectory_data,
        seg_data=seg_data,
        seg_tree=seg_tree,
        panorama_gdf=panorama_gdf,
        poi_gdf=poi_gdf,
        output_path=output_geojson,
        mode=args.mode,
    )

    # Step 8: 生成可视化器
    if not args.no_viewer:
        html_path = generate_viewer(output_geojson)
        log.info(f"\n{'=' * 60}")
        log.info(f"✅ 完成！输出文件:")
        log.info(f"  GeoJSON: {output_geojson}")
        log.info(f"  HTML:    {html_path}")
        log.info(f"  在浏览器中打开 HTML 文件即可查看交互式城市数字孪生")
        log.info(f"{'=' * 60}")
    else:
        log.info(f"\n✅ 完成！GeoJSON: {output_geojson}")


if __name__ == "__main__":
    main()
