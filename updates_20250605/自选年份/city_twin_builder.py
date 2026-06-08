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
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon, MultiLineString, MultiPolygon
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

ROAD_CLASS_ZH = {
    "motorway":       "高速公路",
    "trunk":          "主干道",
    "primary":        "一级道路",
    "secondary":      "二级道路",
    "tertiary":       "三级道路",
    "residential":    "居住区道路",
    "unclassified":   "未分类道路",
    "service":        "服务性道路",
    "cycleway":       "自行车道",
    "footway":        "步行道",
    "path":           "小径",
    "track":          "乡村道路",
    "steps":          "台阶",
    "pedestrian":     "步行街",
    "living_street":  "生活街道",
}

BUILDING_DENSITY_ZH = {
    "low":    "稀疏",
    "medium": "中等",
    "high":   "稠密",
}

FACILITY_NAMES = {
    # 英文 key → 中文显示名
    "school":       "学校",
    "hospital":     "医院/诊所",
    "park":         "公园/绿化",
    "market":       "超市/市场",
    "metro":        "地铁站",
    "bus":          "公交站",
    # 中文 key → 中文显示名（直接用中文名，无映射必要）
    "学校":         "学校",
    "医院":         "医院/诊所",
    "诊所":         "医院/诊所",
    "公园":         "公园/绿化",
    "超市":         "超市/市场",
    "菜市场":       "超市/市场",
    "市场":         "超市/市场",
    "地铁站":       "地铁站",
    "公交站":       "公交站",
    # POI 详细类别（中文名）→ 中文显示名
    "购物服务":     "购物服务",
    "餐饮服务":     "餐饮服务",
    "教育培训":     "教育培训",
    "医疗保健":     "医疗保健",
    "交通设施":     "交通设施",
    "公共设施":     "公共设施",
    "公司企业":     "公司企业",
    "政府机构":     "政府机构",
    "商务写字楼":   "商务写字楼",
    "住宿服务":     "住宿服务",
    "酒店住宿":     "住宿服务",
    "生活服务":     "生活服务",
    "休闲娱乐":     "休闲娱乐",
    "风景名胜":     "风景名胜",
    "金融保险":     "金融保险",
    "体育休闲":     "体育休闲",
    "汽车服务":     "汽车服务",
    "其他":         "其他",
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
    """加载官方建筑数据，优先保留真实建筑面轮廓，仅在点数据时回退为点要素"""
    if geojson_path is None:
        preferred = DATA_DIR / "nanshan_buildings_v2.geojson"
        fallback = DATA_DIR / "nanshan_buildings_official.geojson"
        geojson_path = preferred if preferred.exists() else fallback

    if not Path(geojson_path).exists():
        log.warning(f"  建筑文件不存在: {geojson_path}，跳过")
        return None

    log.info(f"Step 1: 加载建筑楼栋数据...")
    gdf = gpd.read_file(geojson_path)
    log.info(f"  加载楼栋: {len(gdf):,} 个")
    log.info(f"  CRS: {gdf.crs}")

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    gdf = gdf[gdf.geometry.notnull()].copy()
    geom_types = gdf.geometry.geom_type.astype(str)
    polygon_mask = geom_types.isin(["Polygon", "MultiPolygon"])
    point_mask = geom_types == "Point"

    if polygon_mask.any():
        poly_count = int(polygon_mask.sum())
        point_count = int(point_mask.sum())
        other_count = int((~polygon_mask & ~point_mask).sum())
        log.info(f"  检测到真实建筑面: {poly_count:,} 个")
        if point_count:
            log.info(f"  同时检测到建筑点: {point_count:,} 个")
        if other_count:
            log.info(f"  忽略其他几何类型: {other_count:,} 个")

        gdf = gdf[polygon_mask].copy()
        gdf.geometry = gdf.geometry.buffer(0)
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()

        centroid_series = gdf.to_crs(epsg=3857).geometry.centroid
        centroid_wgs84 = gpd.GeoSeries(centroid_series, crs="EPSG:3857").to_crs(epsg=4326)
        gdf["lon"] = centroid_wgs84.x
        gdf["lat"] = centroid_wgs84.y
    else:
        log.info("  未检测到建筑面，回退为点建筑数据")
        gdf = gdf[point_mask].copy()
        gdf["lon"] = gdf.geometry.x
        gdf["lat"] = gdf.geometry.y

    floors_source = gdf["floors"] if "floors" in gdf.columns else gdf.get("levels")
    if floors_source is None:
        floors_source = pd.Series([1] * len(gdf), index=gdf.index)
    gdf["floors"] = pd.to_numeric(floors_source, errors="coerce").fillna(1).clip(1, 100)
    gdf["height_m"] = gdf["floors"] * FLOOR_HEIGHT_M
    use_type_source = gdf["use_type"] if "use_type" in gdf.columns else pd.Series([9] * len(gdf), index=gdf.index)
    gdf["use_type"] = pd.to_numeric(use_type_source, errors="coerce").fillna(9).astype(int)

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
# Step 2: 建筑几何标准化（优先保留真实建筑面，点数据才动态缓冲）
# ============================================================
def buildings_to_polygons(buildings_gdf, base_buffer_m=30):
    """标准化建筑几何：真实面直接保留，点数据再按楼层动态缓冲生成面"""
    if buildings_gdf is None:
        return None

    gdf = buildings_gdf.copy()
    geom_types = gdf.geometry.geom_type.astype(str)
    polygon_mask = geom_types.isin(["Polygon", "MultiPolygon"])

    if polygon_mask.all():
        log.info("Step 2: 建筑几何标准化 (保留真实建筑轮廓)...")
        gdf.geometry = gdf.geometry.buffer(0)
        gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty].copy()
        log.info(f"  保留 {len(gdf):,} 个真实建筑面")
        return gdf

    log.info(f"Step 2: 建筑点转面 (动态缓冲)...")

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
            # 优先用 name，其次 fclass_cn（中文路类），最后用 fclass
            road_name = (
                row.get("name") if str(row.get("name", "").strip()) not in ("", "None", "nan")
                else row.get("fclass_cn") if str(row.get("fclass_cn", "").strip()) not in ("", "None", "nan")
                else row.get("fclass", "未知道路")
            )
            road_type = (
                row.get("fclass_cn") if str(row.get("fclass_cn", "").strip()) not in ("", "None", "nan")
                else row.get("fclass", "未知")
            )
            props = {
                "layer": "road",
                "fclass": row.get("fclass", "unknown"),
                "name": road_name,
                "road_type": road_type,
                "oneway": row.get("oneway", ""),
                "length_m": row.get("length_m", None),
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

            # 建筑名称：优先用 addr（地址），其次用 name，最后用 use_name（用途）
            raw_name = str(row.get("name", "").strip())
            raw_addr = str(row.get("addr", "").strip())
            raw_use = str(row.get("use_name", "")).strip()
            # use_name 格式通常是 "科教/education"，只取中文部分
            use_zh = raw_use.split("/")[0] if "/" in raw_use else raw_use
            if raw_addr and raw_addr not in ("", "None", "nan"):
                bld_name = raw_addr
            elif raw_name and raw_name not in ("", "None", "nan"):
                bld_name = raw_name
            else:
                bld_name = use_zh + "建筑" if use_zh else "未知道建筑"

            props = {
                "layer": "building",
                "floors": int(row.get("floors", 1)),
                "height_m": float(row.get("height_m", 3)),
                "use_type": int(row.get("use_type", 9)),
                "use_name": use_zh if use_zh else "其他",
                "name": bld_name,
                "addr": raw_addr if raw_addr not in ("", "None", "nan") else "",
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

            # urban_form 翻译 + 楼层信息
            uf = str(row.get("urban_form", ""))
            uf_zh = str(row.get("urban_form_zh", "")).strip()
            if uf_zh and uf_zh not in ("", "None", "nan"):
                urban_label = uf_zh
            elif uf == "HighRise":
                urban_label = "高层"
            elif uf == "MidRise":
                urban_label = "多层"
            elif uf == "LowRise":
                urban_label = "低层"
            elif uf == "Sparse":
                urban_label = "稀疏"
            else:
                urban_label = "未知"

            props = {
                "layer": "trajectory",
                "pt_id": int(row.get("pt_id", 0)),
                "fclass": str(row.get("fclass", "")),
                "fclass_cn": ROAD_CLASS_ZH.get(str(row.get("fclass", "")), "其他道路"),
                "building_density": str(row.get("building_density", "")),
                "building_density_zh": BUILDING_DENSITY_ZH.get(str(row.get("building_density", "")), "未知"),
                "urban_form": str(row.get("urban_form", "")),
                "urban_label": urban_label,
                "avg_floors": float(row.get("nearby_floors_avg", 0)) if not pd.isna(row.get("nearby_floors_avg")) else 0,
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
            # POI 设施中文类别名
            ft = str(row.get("facility_type", ""))
            ft_cn = FACILITY_NAMES.get(ft, ft)
            raw_addr = str(row.get("addr", "") if "addr" in row else row.get("address", "")).strip()
            raw_lon = row.get("lon") or row.get("lng") or row.get("longitude")
            raw_lat = row.get("lat") if "lat" in row else row.get("latitude")

            props = {
                "layer": "poi",
                "name": str(row.get("name", "")),
                "category1": str(row.get("category1", "")),
                "category2": str(row.get("category2", "")),
                "facility_type": ft,
                "facility_type_cn": ft_cn,
                "addr": raw_addr if raw_addr not in ("", "None", "nan") else "",
                "lon": float(raw_lon) if raw_lon else None,
                "lat": float(raw_lat) if raw_lat else None,
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
    """生成 Leaflet 交互式 HTML 可视化器（分文件存储避免浏览器卡顿）"""
    if output_html is None:
        output_html = OUT_DIR / "city_twin_viewer.html"

    log.info(f"\n生成交互式可视化器: {output_html}")

    # 读取 GeoJSON
    with open(geojson_path, "r", encoding="utf-8") as f:
        fc = json.load(f)

    # 分离：轨迹和道路都不阻塞首屏。核心层先加载，路网作为后台/按需图层加载。
    base_features = [f for f in fc["features"]
                    if f["properties"].get("layer") not in ("trajectory",)]
    traj_features = [f for f in fc["features"]
                     if f["properties"].get("layer") == "trajectory"]
    road_features = [f for f in base_features
                     if f["properties"].get("layer") == "road"]
    core_features = [f for f in base_features
                     if f["properties"].get("layer") != "road"]
    building_features = [f for f in core_features
                         if f["properties"].get("layer") == "building"]

    base_fc = {"type": "FeatureCollection", "features": base_features}
    core_fc = {"type": "FeatureCollection", "features": core_features}
    roads_fc = {"type": "FeatureCollection", "features": road_features}
    traj_fc = {"type": "FeatureCollection", "features": traj_features}
    buildings_fc = {"type": "FeatureCollection", "features": building_features}

    # 写单独文件供 viewer fetch。base_data.json 保留为全量底图兼容文件。
    base_path = OUT_DIR / "base_data.json"
    with open(base_path, "w", encoding="utf-8") as f:
        json.dump(base_fc, f)
    log.info(f"  兼容底图数据写入: {base_path} ({len(base_features):,} 要素)")

    core_path = OUT_DIR / "base_core_data.json"
    with open(core_path, "w", encoding="utf-8") as f:
        json.dump(core_fc, f)
    log.info(f"  首屏核心数据写入: {core_path} ({len(core_features):,} 要素)")

    roads_path = OUT_DIR / "roads_data.json"
    with open(roads_path, "w", encoding="utf-8") as f:
        json.dump(roads_fc, f)
    log.info(f"  道路后台数据写入: {roads_path} ({len(road_features):,} 要素)")

    traj_path = OUT_DIR / "trajectory_data.json"
    with open(traj_path, "w", encoding="utf-8") as f:
        json.dump(traj_fc, f)
    log.info(f"  轨迹数据写入: {traj_path} ({len(traj_features):,} 点)")

    buildings_path = OUT_DIR / "buildings_white_model.json"
    with open(buildings_path, "w", encoding="utf-8") as f:
        json.dump(buildings_fc, f)
    log.info(f"  白模建筑数据写入: {buildings_path} ({len(building_features):,} 要素)")

    metadata = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "source_geojson": Path(geojson_path).name,
        "counts": {
            "features_total": len(fc.get("features", [])),
            "core_features": len(core_features),
            "buildings": len(building_features),
            "roads": len(road_features),
            "trajectories": len(traj_features),
        },
        "artifacts": {
            "base_data": base_path.name,
            "base_core_data": core_path.name,
            "roads_data": roads_path.name,
            "trajectory_data": traj_path.name,
            "buildings_white_model": buildings_path.name,
            "viewer_html": Path(output_html).name,
        },
    }
    metadata_path = OUT_DIR / "city_twin_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    log.info(f"  元数据写入: {metadata_path}")

    # 写 HTML（通过 fetch 加载外部 JSON，不内嵌大数据）
    html_content = _build_viewer_html(
        data=None,
        traj_data=None,
        base_filename=core_path.name,
        roads_filename=roads_path.name,
        traj_filename=traj_path.name,
    )
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
    log.info(f"  提示: HTML 依赖同目录下的 base_data.json 和 trajectory_data.json")
    return output_html

    return output_html


def _build_viewer_html(data=None, traj_data=None, base_filename=None, roads_filename=None, traj_filename=None):
    """
    生成 Leaflet 交互式可视化 HTML。
    所有数据通过 fetch 异步加载，避免 HTML 文件过大。
    base_filename 和 traj_filename 相对于 HTML 文件路径。
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
<link rel="stylesheet" href="https://unpkg.com/leaflet-minimap@3.6.1/dist/Control.MiniMap.min.css" />

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
.ctrl-btn-sm {
    padding: 2px 7px;
    background: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 4px;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.15s;
    white-space: nowrap;
}
.ctrl-btn-sm.active {
    background: #1f3a5f;
    color: #58a6ff;
    border-color: #388bfd;
    font-weight: 600;
}
}
.ctrl-btn-sm:hover { border-color: #58a6ff; color: #e6edf3; }
.spinner-sm {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid #30363d;
    border-top-color: #58a6ff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
}

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

/* 轨迹 MarkerCluster 圆圈样式 */
.traj-cluster {
    background: transparent !important;
    border: none !important;
}

/* 迷你地图样式微调 */
.leaflet-control-minimap {
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    overflow: hidden;
}

/* 加载中覆盖层 */
#loading {
    position: fixed;
    inset: 0;
    background: rgba(13,17,23,0.85);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    transition: opacity 0.4s;
}
#loading.hidden {
    opacity: 0;
    pointer-events: none;
}
#loading .spinner {
    width: 40px; height: 40px;
    border: 3px solid #30363d;
    border-top-color: #58a6ff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin-bottom: 12px;
}
@keyframes spin { to { transform: rotate(360deg); } }
#loading p { font-size: 13px; color: #8b949e; }

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
                <span class="layer-name">🛣️ 路网<span class="layer-indicator" id="ind-roads">后台</span></span>
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
                点击地图任意位置，查看步行可达设施列表
            </div>
            <!-- 半径切换 -->
            <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:8px;">
                <button class="ctrl-btn active" id="circle-btn-500" onclick="setWalkCircle(500)">500m</button>
                <button class="ctrl-btn" id="circle-btn-1000" onclick="setWalkCircle(1000)">1km</button>
                <button class="ctrl-btn" id="circle-btn-1500" onclick="setWalkCircle(1500)">1.5km</button>
            </div>

            <!-- 设施类型过滤器 -->
            <div id="poi-filters" style="display:none;margin-bottom:6px;">
                <div style="font-size:10px;color:#8b949e;margin-bottom:3px;">筛选:</div>
                <div style="display:flex;gap:3px;flex-wrap:wrap;" id="filter-chips"></div>
            </div>

            <!-- 汇总行 -->
            <div id="circle-summary" style="font-size:11px;color:#e6edf3;padding:6px 8px;background:#21262d;border-radius:4px;margin-bottom:6px;display:none;">
                <span id="circle-total"></span>
            </div>

            <!-- 设施列表（可滚动） -->
            <div id="poi-list" style="display:none;max-height:320px;overflow-y:auto;border-radius:4px;background:#161b22;border:1px solid #30363d;">
                <div id="poi-list-inner"></div>
            </div>

            <!-- 清除按钮 -->
            <div style="margin-top:8px;">
                <button onclick="clearWalkCircle()" style="background:#21262d;color:#e6edf3;border:1px solid #30363d;padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;width:100%;">清除</button>
            </div>
        </div>

        <!-- ═══════════════════════════════════════════════════ -->
        <!-- 路由分析面板（对接 FastAPI 后端） -->
        <!-- ═══════════════════════════════════════════════════ -->
        <div class="section">
            <div class="section-title">🛤️ 路径规划</div>
            <div style="font-size:11px;color:#8b949e;margin-bottom:8px;">
                点击地图设置起点，自动规划到最近设施的步行路线
            </div>

            <!-- 起点/终点 -->
            <div style="display:flex;gap:6px;margin-bottom:8px;">
                <div style="flex:1;">
                    <div style="font-size:10px;color:#6e7681;margin-bottom:2px;">起点</div>
                    <div id="route-from" style="background:#21262d;border:1px solid #30363d;border-radius:4px;padding:5px 8px;font-size:11px;color:#e6edf3;min-height:18px;">
                        <span style="color:#6e7681">点击地图选择</span>
                    </div>
                </div>
                <div style="display:flex;align-items:center;padding-top:18px;color:#6e7681;">→</div>
                <div style="flex:1;">
                    <div style="font-size:10px;color:#6e7681;margin-bottom:2px;">终点</div>
                    <div id="route-to" style="background:#21262d;border:1px solid #30363d;border-radius:4px;padding:5px 8px;font-size:11px;color:#e6edf3;min-height:18px;">
                        <span style="color:#6e7681">点击设施选择</span>
                    </div>
                </div>
            </div>

            <!-- 快捷设施按钮 -->
            <div style="font-size:10px;color:#6e7681;margin-bottom:4px;">快速选择终点类型:</div>
            <div style="display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px;">
                <button class="ctrl-btn-sm" onclick="selectDestination('school')" title="学校">🏫 学校</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('hospital')" title="医疗">🏥 医疗</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('park')" title="公园">🌳 公园</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('market')" title="菜市场">🛒 菜场</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('transit')" title="交通">🚌 交通</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('restaurant')" title="餐饮">🍜 餐饮</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('shopping')" title="购物">🛍️ 购物</button>
                <button class="ctrl-btn-sm" onclick="selectDestination('bank')" title="金融">🏦 金融</button>
            </div>

            <!-- 等时圈阈值 -->
            <div style="font-size:10px;color:#6e7681;margin-bottom:4px;">等时圈阈值:</div>
            <div style="display:flex;gap:4px;margin-bottom:8px;">
                <button class="ctrl-btn active" id="iso-btn-10" onclick="setIsochrone(10)">10分钟</button>
                <button class="ctrl-btn" id="iso-btn-15" onclick="setIsochrone(15)">15分钟</button>
                <button class="ctrl-btn" id="iso-btn-20" onclick="setIsochrone(20)">20分钟</button>
            </div>

            <!-- 等时圈显示开关 -->
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;color:#8b949e;">
                    <input type="checkbox" id="toggle-isochrone" onchange="toggleIsochrone()" checked>
                    <span>显示等时圈</span>
                </label>
                <label style="display:flex;align-items:center;gap:5px;cursor:pointer;font-size:11px;color:#8b949e;">
                    <input type="checkbox" id="toggle-route" onchange="toggleRoute()" checked>
                    <span>显示路线</span>
                </label>
            </div>

            <!-- 规划按钮 -->
            <div style="display:flex;gap:6px;margin-bottom:8px;">
                <button onclick="planRoute()" style="flex:1;background:#238636;color:#fff;border:none;padding:6px 10px;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;">
                    🚶 规划步行路线
                </button>
                <button onclick="computeIsochrone()" style="flex:1;background:#1f6feb;color:#fff;border:none;padding:6px 10px;border-radius:4px;font-size:12px;font-weight:600;cursor:pointer;">
                    🕐 计算等时圈
                </button>
            </div>

            <!-- 路线结果 -->
            <div id="route-result" style="display:none;background:#161b22;border:1px solid #30363d;border-radius:4px;padding:8px;">
                <div id="route-result-header" style="font-size:11px;color:#e6edf3;margin-bottom:6px;"></div>
                <div id="route-result-body" style="max-height:200px;overflow-y:auto;"></div>
            </div>

            <!-- 加载状态 -->
            <div id="route-loading" style="display:none;text-align:center;padding:10px;">
                <div class="spinner-sm"></div>
                <div style="font-size:11px;color:#8b949e;margin-top:4px;">规划中...</div>
            </div>

            <!-- 清除路由 -->
            <div style="margin-top:6px;">
                <button onclick="clearAllRoute()" style="background:#21262d;color:#8b949e;border:1px solid #30363d;padding:4px 10px;border-radius:4px;font-size:11px;cursor:pointer;width:100%;">清除所有</button>
            </div>
        </div>
    </div>

    <div id="map"></div>
</div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.4.1/dist/leaflet.markercluster.js"></script>
<script src="https://unpkg.com/leaflet-minimap@3.6.1/dist/Control.MiniMap.min.js"></script>

<script>
// ============================================================
// 地图初始化
// ============================================================
const map = L.map('map', {
    center: [22.53, 113.94],
    zoom: 14,
    zoomControl: true,
    preferCanvas: true,
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

// 小地图（鹰眼）
const miniBase = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 });
new L.Control.MiniMap(miniBase, { toggleDisplay: true, minimized: false, position: 'bottomleft' }).addTo(map);

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
    // 扩展类型（路网分析返回）
    shopping: '#E91E63',
    restaurant: '#FF5722',
    transit: '#00BCD4',
    public: '#607D8B',
    company: '#795548',
    government: '#37474F',
    office: '#9E9E9E',
    hotel: '#8D6E63',
    life: '#A1887F',
    entertainment: '#CE93D8',
    car: '#90A4AE',
    sports: '#4DD0E1',
    bank: '#FFD54F',
    tourism: '#FF8A65',
    other: '#BDBDBD',
    // 中文类别（POI层直接用中文名）
    '购物服务': '#E91E63',
    '餐饮服务': '#FF5722',
    '教育培训': '#4CAF50',
    '医疗保健': '#F44336',
    '交通设施': '#00BCD4',
    '公共设施': '#607D8B',
    '公司企业': '#795548',
    '政府机构': '#37474F',
    '商务写字楼': '#9E9E9E',
    '住宿服务': '#8D6E63',
    '酒店住宿': '#8D6E63',
    '生活服务': '#A1887F',
    '休闲娱乐': '#CE93D8',
    '其他': '#BDBDBD',
};
const FACILITY_NAMES_JS = {
    school: '学校/科教',
    hospital: '医疗保健',
    park: '公园绿化',
    market: '菜市场',
    metro: '地铁站',
    bus: '公交站',
    // 扩展类型
    shopping: '购物服务',
    restaurant: '餐饮服务',
    transit: '交通设施',
    public: '公共设施',
    company: '公司企业',
    government: '政府机构',
    office: '商务写字楼',
    hotel: '住宿服务',
    life: '生活服务',
    entertainment: '休闲娱乐',
    car: '汽车相关',
    sports: '运动健身',
    bank: '金融机构',
    tourism: '旅游景点',
    other: '其他',
    // 中文类别（POI层直接用中文名）
    '购物服务': '购物服务',
    '餐饮服务': '餐饮服务',
    '教育培训': '教育培训',
    '医疗保健': '医疗保健',
    '交通设施': '交通设施',
    '公共设施': '公共设施',
    '公司企业': '公司企业',
    '政府机构': '政府机构',
    '商务写字楼': '商务写字楼',
    '住宿服务': '住宿服务',
    '酒店住宿': '酒店住宿',
    '生活服务': '生活服务',
    '休闲娱乐': '休闲娱乐',
    '其他': '其他',
};

// ============================================================
// 数据层：通过 fetch 异步加载外部 JSON 文件
// ============================================================
let BASE_DATA = null;
let ROADS_DATA = null;
let TRAJ_DATA = null;
let buildings = [], roads = [], panorama = [], poi = [];
let colorMode = 'walkability'; // 建筑着色模式
let roadsLoaded = false;
let roadsLoading = false;
const CORE_DATA_URL = './""" + (base_filename or "base_core_data.json") + """';
const ROADS_DATA_URL = './""" + (roads_filename or "roads_data.json") + """';
const TRAJ_DATA_URL = './""" + (traj_filename or "trajectory_data.json") + """';

function fetchJson(url) {
    return fetch(url, { cache: 'force-cache', headers: { 'Accept': 'application/json' } })
        .then(r => {
            if (!r.ok) throw new Error(`${url} 返回 ${r.status}`);
            return r.json();
        });
}

function updateStatsBar(trajectoryText) {
    const trajText = trajectoryText || document.getElementById('ind-trajectory').textContent || '-';
    document.getElementById('stats-bar').textContent =
        `🏢 ${buildings.length.toLocaleString()} 栋 | 🛣️ ${roads.length.toLocaleString()} 条 | 📍 轨迹 ${trajText} | 🗼 全景 ${panorama.length.toLocaleString()}`;
}

function loadBaseThenTraj() {
    fetchJson(CORE_DATA_URL)
        .then(data => {
            BASE_DATA = data;
            buildings = (data.features || []).filter(f => f.geometry.type === 'Polygon');
            roads = (data.features || []).filter(f => f.properties && f.properties.layer === 'road');
            panorama = (data.features || []).filter(f => f.geometry.type === 'Point' && f.properties.layer === 'panorama');
            poi = (data.features || []).filter(f => f.geometry.type === 'Point' && f.properties.layer === 'poi');
            initLayers();
            window.setTimeout(loadRoadsLayerDeferred, 700);
            fetchJson(TRAJ_DATA_URL)
                .then(traj => {
                    TRAJ_DATA = traj;
                    initTrajectoryLayer();
                })
                .catch(() => { document.getElementById('ind-trajectory').textContent = '0'; });
        })
        .catch(err => {
            console.error('加载底图数据失败:', err);
            document.getElementById('loading').classList.add('hidden');
        });
}

function initLayers() {
    document.getElementById('ind-buildings').textContent = buildings.length.toLocaleString();
    document.getElementById('ind-roads').textContent = roads.length ? roads.length.toLocaleString() : '后台';
    document.getElementById('ind-trajectory').textContent = '-';
    document.getElementById('ind-panorama').textContent = panorama.length.toLocaleString();
    document.getElementById('ind-poi').textContent = poi.length.toLocaleString();
    updateStatsBar('加载中...');

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
if (roadTypes.length === 0) {
    roadLegend.innerHTML = '<div class="legend-item"><div class="legend-color" style="background:#7b8794"></div><span>道路图层后台加载中</span></div>';
}

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
            renderer: L.canvas({ padding: 0.5 }),
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
                layer.bindTooltip(`🛣️ ${f.properties.road_type || f.properties.fclass || '未知道路'} ${f.properties.name || ''}`, {sticky: false, className: 'leaflet-tooltip-dark'});
            }
        });
        layerToggles.roads.layer = layerRoads;
        layerRoads.addTo(map);
    }

    // 全景点层
    if (panorama.length > 0) {
        layerPanorama = L.geoJSON({ type: 'FeatureCollection', features: panorama }, {
            pointToLayer: (f, latlng) => {
                return L.circleMarker(latlng, {
                    radius: 6,
                    fillColor: '#a371f7',
                    color: '#8b5f6',
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
                const ftCn = FACILITY_NAMES_JS[ft] || ft;
                layer.bindTooltip(
                    `<b>${p.name || '设施'}</b><br>${p.category1 || ''} ${p.category2 || ''}<br><span style="color:${FACILITY_COLORS_JS[ft] || '#888'}">${ftCn}</span>`,
                    {sticky: false, className: 'leaflet-tooltip-dark'}
                );
                layer.on('click', () => showInfoPanel('poi', p));
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
                const color = ws != null ? getWalkabilityColor(parseFloat(ws)*10) : '#484f58';
                return { fillColor: color, color: color, weight: 0.3, fillOpacity: 0.6, opacity: 0.3 };
            } else {
                const color = USE_COLORS[p.use_type] || '#b4b4b4';
                return { fillColor: color, color: '#ffffff44', weight: 0.5, fillOpacity: 0.7, opacity: 0.5 };
            }
        },
        onEachFeature: (f, layer) => {
            const p = f.properties;
            const ws = p.walkability;
            const wsStr = ws != null ? `${(parseFloat(ws)*10).toFixed(1)}/10` : 'N/A';
            const color = ws != null ? getWalkabilityColor(parseFloat(ws)*10) : '#484f58';
            const nameOrAddr = p.name || p.addr || (p.use_name ? p.use_name + '建筑' : '未知道建筑');
            layer.bindTooltip(
                `🏢 ${nameOrAddr}<br>${p.use_name || '其他'} | ${p.floors || 1}层 | ${p.height_m ? parseFloat(p.height_m).toFixed(0) + 'm' : '-'}<br>可达性: <span style="color:${color}">${wsStr}</span>`,
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
}

function loadRoadsLayerDeferred() {
    if (roadsLoaded || roadsLoading) return;
    roadsLoading = true;
    const roadLegend = document.getElementById('legend-roads');
    if (roadLegend) {
        roadLegend.innerHTML = '<div class="legend-item"><div class="legend-color" style="background:#7b8794"></div><span>道路图层加载中</span></div>';
    }
    fetchJson(ROADS_DATA_URL)
        .then(data => {
            ROADS_DATA = data;
            roads = (data.features || []).filter(f => f.properties && f.properties.layer === 'road');
            roadsLoaded = true;
            renderRoadLayer();
            document.getElementById('ind-roads').textContent = roads.length.toLocaleString();
            updateStatsBar();
        })
        .catch(err => {
            console.warn('道路图层加载失败:', err);
            if (roadLegend) {
                roadLegend.innerHTML = '<div class="legend-item"><div class="legend-color" style="background:#da3633"></div><span>道路图层加载失败</span></div>';
            }
        })
        .finally(() => {
            roadsLoading = false;
        });
}

function renderRoadLayer() {
    if (!roads.length) return;
    if (layerRoads && map.hasLayer(layerRoads)) {
        map.removeLayer(layerRoads);
    }
    const roadTypes = [...new Set(roads.map(f => f.properties.fclass))];
    const roadLegend = document.getElementById('legend-roads');
    if (roadLegend) {
        roadLegend.innerHTML = roadTypes.map(fc => {
            const color = ROAD_COLORS[fc] || '#7b8794';
            return `<div class="legend-item">
                <div class="legend-color" style="background:${color}"></div>
                <span>${fc || 'unknown'}</span>
            </div>`;
        }).join('');
    }
    layerRoads = L.geoJSON({ type: 'FeatureCollection', features: roads }, {
        renderer: L.canvas({ padding: 0.5 }),
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
            layer.bindTooltip(`🛣️ ${f.properties.road_type || f.properties.fclass || '未知道路'} ${f.properties.name || ''}`, {sticky: false, className: 'leaflet-tooltip-dark'});
        }
    });
    layerToggles.roads.layer = layerRoads;
    const roadsToggle = document.getElementById('toggle-roads');
    if (!roadsToggle || roadsToggle.checked) {
        layerRoads.addTo(map);
    }
}

// 轨迹层（异步加载 + MarkerCluster 聚合）
let trajectoryLoaded = false;
let trajectoryMarkers = null;
let trajectoryClusterGroup = null;

function getMaxTrajPointsForZoom(zoom) {
    if (zoom >= 16) return 50000;
    if (zoom >= 15) return 20000;
    if (zoom >= 14) return 10000;
    if (zoom >= 13) return 5000;
    if (zoom >= 12) return 2000;
    if (zoom >= 11) return 1000;
    return 500;
}

function getTrajColor(ws) {
    if (ws == null || ws === '') return '#58a6ff';
    const score = parseFloat(ws);
    if (isNaN(score)) return '#58a6ff';
    const t = Math.max(0, Math.min(1, score));
    if (t < 0.4) return `rgb(255,${Math.round(120 + 135*t/0.4)},80)`;
    if (t < 0.7) return `rgb(${Math.round(255 - 255*(t-0.4)/0.3)},${Math.round(255 - 135*(t-0.4)/0.3)},80)`;
    return `rgb(${Math.round(255*(1-t)/0.3)},255,${Math.round(80 + 175*t/0.3)})`;
}

function getTrajLabel(p) {
    const road = p.fclass_cn || p.fclass || '未知道路';
    const urban = p.urban_label || p.urban_form || '';
    const density = p.building_density_zh || p.building_density || '';
    const floors = p.avg_floors ? `${p.avg_floors.toFixed(1)}层` : '';
    const ws = p.walkability;
    const wsStr = ws != null && ws !== '' ? `${(parseFloat(ws)*10).toFixed(1)}/10` : 'N/A';
    return `📍 轨迹 #${p.pt_id}\n道路: ${road} ${p.name||''}\n形态: ${urban} ${floors}\n密度: ${density}\n可达性: ${wsStr}`;
}

function loadTrajectoryPoints(limit) {
    if (!TRAJ_DATA || !TRAJ_DATA.features) return [];
    return TRAJ_DATA.features.slice(0, Math.min(limit, TRAJ_DATA.features.length));
}

function initTrajectoryLayer() {
    if (!TRAJ_DATA || !TRAJ_DATA.features || TRAJ_DATA.features.length === 0) {
        document.getElementById('ind-trajectory').textContent = '0';
        updateStatsBar('0');
        return;
    }
    const zoom = map.getZoom();
    const maxPts = getMaxTrajPointsForZoom(zoom);
    renderTrajectoryPoints(maxPts);
    layerToggles.trajectory = { layer: trajectoryClusterGroup, visible: true, defaultOpacity: 0.9 };
}

function renderTrajectoryPoints(maxPoints) {
    const pts = loadTrajectoryPoints(maxPoints);
    if (trajectoryClusterGroup) {
        map.removeLayer(trajectoryClusterGroup);
        trajectoryClusterGroup = null;
    }
    trajectoryClusterGroup = L.markerClusterGroup({
        chunkedLoading: true,
        chunkInterval: 100,
        chunkDelay: 50,
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: false,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        iconCreateFunction: function(cluster) {
            const count = cluster.getChildCount();
            const size = count < 100 ? 'small' : count < 500 ? 'medium' : 'large';
            const r = size === 'small' ? 30 : size === 'medium' ? 40 : 50;
            return L.divIcon({
                html: `<div style="background:rgba(88,166,255,0.85);border-radius:50%;width:${r}px;height:${r}px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;font-weight:700;border:2px solid rgba(255,255,255,0.4);box-shadow:0 2px 8px rgba(0,0,0,0.4);">${count>=1000?(count/1000).toFixed(0)+'k':count}</div>`,
                className: 'traj-cluster',
                iconSize: [r, r],
                iconAnchor: [r/2, r/2],
            });
        }
    });
    pts.forEach(f => {
        const latlng = L.latLng(f.geometry.coordinates[1], f.geometry.coordinates[0]);
        const p = f.properties;
        const color = getTrajColor(p.walkability);
        const marker = L.circleMarker(latlng, {
            radius: 4,
            fillColor: color,
            color: '#fff',
            weight: 1,
            fillOpacity: 0.9,
            opacity: 0.9,
        });
        marker.bindTooltip(getTrajLabel(p), {sticky: false, className: 'leaflet-tooltip-dark', direction: 'top'});
        marker.on('click', () => showInfoPanel('trajectory', p));
        trajectoryClusterGroup.addLayer(marker);
    });
    map.addLayer(trajectoryClusterGroup);
    trajectoryLoaded = true;
    const total = TRAJ_DATA && TRAJ_DATA.features ? TRAJ_DATA.features.length : 0;
    document.getElementById('ind-trajectory').textContent = `${pts.length.toLocaleString()}/${total.toLocaleString()}`;
    document.getElementById('stats-bar').textContent =
        `🏢 ${buildings.length.toLocaleString()} 栋 | 🛣️ ${roads.length.toLocaleString()} 条 | 📍 轨迹 ${pts.length.toLocaleString()} | 🗼 全景 ${panorama.length.toLocaleString()}`;
}

// 底图加载完成后，延迟加载轨迹层
map.whenReady(() => {
    setTimeout(() => {
        if (!TRAJ_DATA) return;
        const zoom = map.getZoom();
        const maxPts = getMaxTrajPointsForZoom(zoom);
        renderTrajectoryPoints(maxPts);
        layerToggles.trajectory = { layer: trajectoryClusterGroup, visible: true };
    }, 500);
});

// 缩放时重新渲染轨迹
map.on('zoomend', () => {
    if (!trajectoryLoaded || !TRAJ_DATA) return;
    const zoom = map.getZoom();
    const maxPts = getMaxTrajPointsForZoom(zoom);
    renderTrajectoryPoints(maxPts);
    if (layerToggles.trajectory && layerToggles.trajectory.layer) {
        layerToggles.trajectory.visible = true;
        if (!map.hasLayer(layerToggles.trajectory.layer)) {
            map.addLayer(layerToggles.trajectory.layer);
        }
    }
});

// ============================================================
// 信息面板
// ============================================================
function showInfoPanel(type, p) {
    const panel = document.getElementById('info-panel');
    if (type === 'building') {
        const ws = p.walkability;
        const wsStr = ws != null ? `${(parseFloat(ws)*10).toFixed(1)}/10` : '无数据';
        const wsColor = ws != null ? getWalkabilityColor(parseFloat(ws)*10) : '#484f58';
        panel.innerHTML = `
            <div class="info-row">名称: <span>${p.name || p.addr || p.use_name + '建筑' || '未知道建筑'}</span></div>
            <div class="info-row">地址: <span>${p.addr || '-'}</span></div>
            <div class="info-row">用途: <span>${p.use_name || '其他'}</span></div>
            <div class="info-row">层数: <span>${p.floors || 1} 层</span></div>
            <div class="info-row">高度: <span>${p.height_m ? parseFloat(p.height_m).toFixed(1) + 'm' : '-'}</span></div>
            <div class="info-row">坐标: <span>${p.lon ? parseFloat(p.lon).toFixed(5) + ', ' + parseFloat(p.lat).toFixed(5) : '-'}</span></div>
            <div class="info-row">可达性: <span style="color:${wsColor}">${wsStr}</span></div>
        `;
    } else if (type === 'trajectory') {
        const ws = p.walkability;
        const wsStr = ws != null ? `${(parseFloat(ws)*10).toFixed(1)}/10` : '无数据';
        const wsColor = ws != null ? getWalkabilityColor(parseFloat(ws)*10) : '#484f58';
        panel.innerHTML = `
            <div class="info-row">道路: <span>${p.fclass_cn || p.name || p.fclass || '未知道路'}</span></div>
            <div class="info-row">路名: <span>${p.name || '-'}</span></div>
            <div class="info-row">形态: <span>${p.urban_label || p.urban_form || '未知'}</span></div>
            <div class="info-row">密度: <span>${p.building_density_zh || p.building_density || '未知'}</span></div>
            <div class="info-row">平均层数: <span>${p.avg_floors ? parseFloat(p.avg_floors).toFixed(1) + ' 层' : '-'}</span></div>
            <div class="info-row">朝向: <span>${p.heading_label || p.heading || '-'}</span></div>
            <div class="info-row">可达性: <span style="color:${wsColor}">${wsStr}</span></div>
            <div class="info-row">位置ID: <span>#${p.pt_id || '-'}</span></div>
        `;
    } else if (type === 'panorama') {
        panel.innerHTML = `
            <div class="info-row">地点: <span>${p.township || '-'}</span></div>
            <div class="info-row">道路: <span>${p.road_name || p.name || '-'}</span></div>
            <div class="info-row">朝向: <span>${p.heading || '-'}</span></div>
            <div class="info-row">年份: <span>${p.year || '-'}</span></div>
            <div class="info-row">坐标: <span>${p.lon ? parseFloat(p.lon).toFixed(5) + ', ' + parseFloat(p.lat).toFixed(5) : '-'}</span></div>
        `;
    } else if (type === 'poi') {
        panel.innerHTML = `
            <div class="info-row">名称: <span>${p.name || p.poi_name || '未知设施'}</span></div>
            <div class="info-row">类别: <span>${p.facility_type_cn || p.facility_type || '未知'}</span></div>
            <div class="info-row">地址: <span>${p.addr || p.address || '-'}</span></div>
            <div class="info-row">坐标: <span>${p.lon ? parseFloat(p.lon).toFixed(5) + ', ' + parseFloat(p.lat).toFixed(5) : '-'}</span></div>
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
        if (key === 'roads' && el.checked && !layerToggles.roads.layer) {
            loadRoadsLayerDeferred();
            return;
        }
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
// 15分钟生活圈（步行可达 + 设施详细列表）
// ============================================================
let walkCircleLayer = null;
let walkCircleMarker = null;
let walkCircleRadius = 500;
let clickedLatLng = null;
// 从 POI 数据动态获取所有设施类型作为默认筛选
var defaultActiveFilters = ['学校','医院','诊所','公园','超市','菜市场','市场','地铁站','公交站'];
poi.forEach(function(f) {
    var ft = f.properties.facility_type;
    if (ft && ft.trim() !== '') defaultActiveFilters.push(ft);
});
var uniqueFts = [...new Set(defaultActiveFilters)];
// 去重英文（不重复添加）
var enFts = ['school','hospital','park','market','metro','bus'];
enFts.forEach(function(eft) { if (!uniqueFts.includes(eft)) uniqueFts.push(eft); });
let activeFilters = new Set(uniqueFts);

// 点击地图 → 画圈 + 设施列表
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

function getDirection(fromLat, fromLng, toLat, toLng) {
    const dLon = (toLng - fromLng) * Math.cos(fromLat * Math.PI / 180);
    const dLat = toLat - fromLat;
    const angle = Math.atan2(dLon, dLat) * 180 / Math.PI;
    if (angle < -157.5 || angle >= 157.5) return '北';
    if (angle >= -157.5 && angle < -112.5) return '东北';
    if (angle >= -112.5 && angle < -67.5) return '东';
    if (angle >= -67.5 && angle < -22.5) return '东南';
    if (angle >= -22.5 && angle < 22.5) return '南';
    if (angle >= 22.5 && angle < 67.5) return '西南';
    if (angle >= 67.5 && angle < 112.5) return '西';
    return '西北';
}

function estimateWalkTime(distMeters) {
    const mins = Math.round(distMeters / 83.33);
    return mins < 1 ? '<1分钟' : `${mins}分钟`;
}

function updateCircleInfo(latlng) {
    const summaryDiv = document.getElementById('circle-summary');
    const listDiv = document.getElementById('poi-list');
    const innerDiv = document.getElementById('poi-list-inner');
    if (!summaryDiv || !listDiv || !innerDiv) return;

    // 过滤器芯片
    const filterDiv = document.getElementById('poi-filters');
    if (filterDiv) filterDiv.style.display = 'block';
    const chipsDiv = document.getElementById('filter-chips');
    if (chipsDiv) {
        const ftList = ['school', 'hospital', 'park', 'market', 'metro', 'bus'];
        chipsDiv.innerHTML = ftList.map(ft => {
            const active = activeFilters.has(ft);
            const color = FACILITY_COLORS_JS[ft] || '#888';
            return `<span onclick="toggleFilter('${ft}', this)" style="
                display:inline-block;padding:2px 7px;border-radius:10px;font-size:10px;cursor:pointer;
                background:${active ? color + '33' : '#21262d'};
                color:${active ? color : '#8b949e'};
                border:1px solid ${active ? color : '#30363d'};
                user-select:none;
            ">${FACILITY_NAMES_JS[ft] || ft}</span>`;
        }).join('');
    }

    // Haversine 精确距离
    const toRad = d => d * Math.PI / 180;
    const lat1 = toRad(latlng.lat), lng1 = toRad(latlng.lng);

    const inPOIs = [];
    poi.forEach(f => {
        const [lon, lat] = f.geometry.coordinates;
        const lat2 = toRad(lat), lng2 = toRad(lon);
        const dLat = lat2 - lat1, dLon = lng2 - lng1;
        const a = Math.sin(dLat/2)**2 + Math.cos(lat1)*Math.cos(lat2)*Math.sin(dLon/2)**2;
        const dist = 2 * 6371000 * Math.asin(Math.sqrt(a));
        if (dist <= walkCircleRadius) {
            inPOIs.push({ f, dist });
        }
    });

    const counts = { school: 0, hospital: 0, park: 0, market: 0, metro: 0, bus: 0 };
    inPOIs.forEach(({ f }) => {
        const ft = f.properties.facility_type;
        if (counts[ft] !== undefined) counts[ft]++;
    });
    const total = inPOIs.length;

    summaryDiv.style.display = 'block';
    const countRows = Object.entries(counts)
        .filter(([, v]) => v > 0)
        .map(([ft, cnt]) => {
            const c = FACILITY_COLORS_JS[ft] || '#888';
            return `<span style="color:${c};white-space:nowrap;margin-right:6px;">${FACILITY_NAMES_JS[ft]||ft}: <b>${cnt}</b>个</span>`;
        }).join('');
    document.getElementById('circle-total').innerHTML =
        `<b>${(walkCircleRadius/1000).toFixed(1)}km</b> 圈内共 <b>${total}</b> 个设施: ${countRows || '无'}`;

    listDiv.style.display = 'block';
    const filtered = inPOIs.filter(({ f }) => activeFilters.has(f.properties.facility_type));

    if (filtered.length === 0) {
        innerDiv.innerHTML = `<div style="padding:16px;text-align:center;color:#8b949e;font-size:12px;">筛选后无设施</div>`;
        return;
    }

    filtered.sort((a, b) => a.dist - b.dist);
    const display = filtered.slice(0, 50);

    innerDiv.innerHTML = display.map(({ f, dist }) => {
        const p = f.properties;
        const ft = p.facility_type || '';
        const color = FACILITY_COLORS_JS[ft] || '#888';
        const dir = getDirection(latlng.lat, latlng.lng, f.geometry.coordinates[1], f.geometry.coordinates[0]);
        const walkTime = estimateWalkTime(dist);
        const name = (p.name || '未知设施').replace(/'/g, "\\'");
        const addr = p.addr || '';
        const ftCn = FACILITY_NAMES_JS[ft] || ft;
        const distStr = dist < 1000 ? dist.toFixed(0) + 'm' : (dist/1000).toFixed(1) + 'km';

        return `<div class="poi-list-item" onclick="setDestFromPoi(${f.geometry.coordinates[1]}, ${f.geometry.coordinates[0]}, '${name}', '${ft}')">
            <div class="poi-list-row1">
                <span class="poi-dot" style="background:${color}"></span>
                <span class="poi-name">${p.name || '未知设施'}</span>
                <span class="poi-dist" style="color:${color}">${distStr}</span>
            </div>
            <div class="poi-list-row2">
                <span class="poi-tag" style="background:${color}22;color:${color};border:1px solid ${color}44">${ftCn}</span>
                <span class="poi-dir">↗ ${dir}</span>
                <span class="poi-walk">🚶 ${walkTime}</span>
            </div>
            ${addr ? `<div class="poi-addr">${addr}</div>` : ''}
        </div>`;
    }).join('');

    if (filtered.length > 50) {
        innerDiv.innerHTML += `<div style="padding:8px;text-align:center;color:#8b949e;font-size:11px;">还有 ${filtered.length - 50} 个设施，点击列表项可定位</div>`;
    }
}

function toggleFilter(ft, el) {
    if (activeFilters.has(ft)) {
        activeFilters.delete(ft);
    } else {
        activeFilters.add(ft);
    }
    if (clickedLatLng) updateCircleInfo(clickedLatLng);
}

function panToPOI(lat, lng, name) {
    map.setView([lat, lng], 17);
    if (walkCircleMarker) walkCircleMarker.setLatLng([lat, lng]);
}

function clearWalkCircle() {
    if (walkCircleLayer) { map.removeLayer(walkCircleLayer); walkCircleLayer = null; }
    if (walkCircleMarker) { map.removeLayer(walkCircleMarker); walkCircleMarker = null; }
    const summaryDiv = document.getElementById('circle-summary');
    const listDiv = document.getElementById('poi-list');
    const filterDiv = document.getElementById('poi-filters');
    if (summaryDiv) summaryDiv.style.display = 'none';
    if (listDiv) listDiv.style.display = 'none';
    if (filterDiv) filterDiv.style.display = 'none';
    clickedLatLng = null;
}

/* ═══════════════════════════════════════════════════════════════
   路由分析 JS（对接 FastAPI 后端 / network.js）
   ═══════════════════════════════════════════════════════════════ */

const ROUTING_API_BASE = window.location.protocol === 'file:'
    ? 'http://127.0.0.1:8765/api'
    : window.location.origin + '/api';
let routeStart = null;
let routeEnd = null;
let isochroneLayer = null;
let routePolyline = null;
let routeStartMarker = null;
let routeEndMarker = null;
let isochroneTimeMin = 10;
let destFacilityType = 'school';
let isochroneVisible = true;
let routeVisible = true;
let closestFacilitiesLayer = null;  // 最近设施图层

function selectDestination(type) {
    destFacilityType = type;
    // 高亮选中按钮
    document.querySelectorAll('.ctrl-btn-sm').forEach(function(b) {
        b.classList.remove('active');
    });
    // 找到对应按钮并高亮
    var btns = document.querySelectorAll('.ctrl-btn-sm');
    var targetMap = {school:0, hospital:1, park:2, market:3, transit:4, restaurant:5, shopping:6, bank:7};
    var idx = targetMap[type];
    if (idx !== undefined && btns[idx]) btns[idx].classList.add('active');
}
function setIsochrone(mins) {
    isochroneTimeMin = mins;
    document.querySelectorAll('[id^="iso-btn-"]').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('iso-btn-' + mins);
    if (btn) btn.classList.add('active');
}
function toggleIsochrone() {
    isochroneVisible = document.getElementById('toggle-isochrone').checked;
    if (isochroneLayer) {
        isochroneLayer.eachLayer(function(l) {
            var op = isochroneVisible ? 0.5 : 0;
            if (l.setOpacity) l.setOpacity(op);
        });
    }
}
function toggleRoute() {
    routeVisible = document.getElementById('toggle-route').checked;
    if (routePolyline) routePolyline.setStyle({ opacity: routeVisible ? 0.9 : 0 });
}
map.on('click', function(e) {
    if (routeEnd) { clearAllRoute(); }
    routeStart = { lon: e.latlng.lng, lat: e.latlng.lat, node_id: null };
    updateRouteUI();
    if (routeStartMarker) map.removeLayer(routeStartMarker);
    routeStartMarker = L.circleMarker([e.latlng.lat, e.latlng.lng], {
        radius: 7, color: '#58a6ff', fillColor: '#fff', fillOpacity: 1, weight: 2,
    }).addTo(map);
    fetchSnappedNode(e.latlng.lng, e.latlng.lat);
    // 自动查找最近 destFacilityType 设施并设为终点
    fetchClosestFacilityOfType(e.latlng.lng, e.latlng.lat, destFacilityType);
});
function fetchSnappedNode(lon, lat) {
    fetch(ROUTING_API_BASE + '/snap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lon: lon, lat: lat })
    }).then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.node_id !== undefined) {
            routeStart.node_id = data.node_id;
            routeStart.lon = data.lon;
            routeStart.lat = data.lat;
        }
    }).catch(function() {});
}
function fetchClosestFacilityOfType(lon, lat, ftype) {
    fetch(ROUTING_API_BASE + '/closest-facilities', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lon: lon, lat: lat, n_per_type: 1 })
    }).then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.facilities && data.facilities.length > 0) {
            // 过滤同类型最近设施
            var match = data.facilities.find(function(f) { return f.facility_type === ftype; });
            if (!match && data.facilities.length > 0) match = data.facilities[0];
            if (match) {
                // 清除旧的最近设施标注
                if (closestFacilitiesLayer) { map.removeLayer(closestFacilitiesLayer); closestFacilitiesLayer = null; }
                // 标注最近设施
                closestFacilitiesLayer = L.layerGroup();
                L.circleMarker([match.lat, match.lon], {
                    radius: 8, color: FACILITY_COLORS_JS[ftype] || '#f0883e',
                    fillColor: '#fff', fillOpacity: 0.8, weight: 2,
                }).bindPopup('<b>' + (match.name || '设施') + '</b><br>' +
                    '步行约 <b>' + (match.walk_time_s / 60).toFixed(1) + '分钟</b><br>' +
                    '约 <b>' + (match.distance_m || 0).toFixed(0) + '米</b><br>' +
                    '<button onclick="confirmRouteDestination()" style="margin-top:4px;padding:2px 8px;cursor:pointer;">设为终点</button>'
                ).addTo(closestFacilitiesLayer).openPopup();
                closestFacilitiesLayer.addTo(map);
                // 自动设为终点并规划路线
                routeEnd = {
                    lon: match.lon, lat: match.lat,
                    name: match.name || '设施',
                    facility_type: match.facility_type || ftype,
                    walk_time_s: match.walk_time_s
                };
                if (routeEndMarker) map.removeLayer(routeEndMarker);
                routeEndMarker = L.circleMarker([match.lat, match.lon], {
                    radius: 7, color: FACILITY_COLORS_JS[match.facility_type] || '#f0883e',
                    fillColor: '#fff', fillOpacity: 1, weight: 2,
                }).addTo(map);
                updateRouteUI();
                planRoute();
            }
        }
    }).catch(function() {});
}
function confirmRouteDestination() {
    if (closestFacilitiesLayer) closestFacilitiesLayer.closeAll();
}
function setDestFromPoi(lat, lng, name, ft) {
    routeEnd = { lon: lng, lat: lat, name: name, facility_type: ft || destFacilityType };
    if (routeEndMarker) map.removeLayer(routeEndMarker);
    routeEndMarker = L.circleMarker([lat, lng], {
        radius: 7, color: FACILITY_COLORS_JS[ft] || '#f0883e',
        fillColor: '#fff', fillOpacity: 1, weight: 2,
    }).addTo(map);
    updateRouteUI();
    if (routeStart) planRoute();
}
function updateRouteUI() {
    var fromEl = document.getElementById('route-from');
    var toEl = document.getElementById('route-to');
    if (!fromEl || !toEl) return;
    if (routeStart) {
        fromEl.innerHTML = '<span style="color:#58a6ff">📍 ' + routeStart.lat.toFixed(5) + ', ' + routeStart.lon.toFixed(5) + '</span>';
    } else {
        fromEl.innerHTML = '<span style="color:#6e7681">点击地图选择起点</span>';
    }
    if (routeEnd) {
        var ftColor = FACILITY_COLORS_JS[routeEnd.facility_type] || '#f0883e';
        var timeStr = routeEnd.walk_time_s ? ('<span style="color:#58a6ff;font-size:10px"> · ' + (routeEnd.walk_time_s / 60).toFixed(1) + '分钟</span>') : '';
        var nameStr = routeEnd.name ? routeEnd.name : '终点';
        var ftName = FACILITY_NAMES_JS[routeEnd.facility_type] || routeEnd.facility_type || '';
        toEl.innerHTML = '<span style="color:' + ftColor + '">🏁 </span>' + nameStr + ' <span style="color:#6e7681;font-size:10px">(' + ftName + ')' + timeStr + '</span>';
    } else {
        toEl.innerHTML = '<span style="color:#6e7681">点击地图选终点(当前:' + (FACILITY_NAMES_JS[destFacilityType] || destFacilityType) + ')</span>';
    }
}
async function planRoute() {
    if (!routeStart || !routeEnd) { return; }
    var loading = document.getElementById('route-loading');
    var result = document.getElementById('route-result');
    if (loading) loading.style.display = 'block';
    if (result) result.style.display = 'none';
    // 已有等时估算时间则立即显示
    if (routeEnd.walk_time_s && !routePolyline) {
        var headerEl = document.getElementById('route-result-header');
        var bodyEl = document.getElementById('route-result-body');
        if (headerEl) headerEl.innerHTML = '🚶 <b>' + (routeEnd.walk_time_s / 60).toFixed(1) + '分钟</b> <span style="color:#58a6ff;font-size:10px">(最近' + (FACILITY_NAMES_JS[routeEnd.facility_type] || routeEnd.facility_type) + ')</span> <span style="color:#6e7681">' + (routeEnd.name || '') + '</span>';
        if (bodyEl) bodyEl.innerHTML = '<div style="color:#8b949e;font-size:11px;padding:4px 0;">正在计算精确路线...</div>';
        if (result) result.style.display = 'block';
    }
    try {
        var resp = await fetch(ROUTING_API_BASE + '/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                from_lon: routeStart.lon, from_lat: routeStart.lat,
                to_lon: routeEnd.lon, to_lat: routeEnd.lat
            })
        });
        var data = await resp.json();
        if (routePolyline) { map.removeLayer(routePolyline); routePolyline = null; }
        if (data.geometry && data.geometry.length > 1) {
            var latlngs = data.geometry.map(function(c) { return [c[1], c[0]]; });
            routePolyline = L.polyline(latlngs, {
                color: '#58a6ff', weight: 5, opacity: routeVisible ? 0.9 : 0,
                lineCap: 'round', lineJoin: 'round',
            }).addTo(map);
            map.fitBounds(routePolyline.getBounds(), { padding: [50, 50] });
        }
        var timeMin = (data.total_time_s / 60).toFixed(1);
        var distKm = (data.total_distance_m / 1000).toFixed(2);
        var headerEl = document.getElementById('route-result-header');
        var bodyEl = document.getElementById('route-result-body');
        if (headerEl) headerEl.innerHTML = '🚶 <b>' + timeMin + '分钟</b>  ' + distKm + 'km  <span style="color:#58a6ff;font-size:10px">' + (FACILITY_NAMES_JS[routeEnd.facility_type] || routeEnd.facility_type || '') + '</span>  <span style="color:#6e7681">' + (routeEnd.name || '') + '</span>';
        if (bodyEl && data.steps && data.steps.length > 0) {
            bodyEl.innerHTML = data.steps.map(function(s) {
                var roadLabel = s.instruction || s.fclass || '路段';
                var timeMin = (s.time_s / 60).toFixed(1);
                var distM = s.length_m >= 1000 ? (s.length_m / 1000).toFixed(2) + 'km' : s.length_m.toFixed(0) + 'm';
                return '<div class="route-result-step"><span class="route-step-icon">🛤️</span><div class="route-step-info"><div class="route-step-name">' + roadLabel + '</div><div class="route-step-meta">' + timeMin + '分钟 · ' + distM + '</div></div></div>';
            }).join('');
        } else if (bodyEl) {
            bodyEl.innerHTML = '<div style="color:#8b949e;font-size:11px;padding:4px 0;">路线几何获取中...</div>';
        }
        if (result) result.style.display = 'block';
    } catch(e) {
        fallbackRouteResult();
    } finally {
        if (loading) loading.style.display = 'none';
    }
}
function fallbackRouteResult() {
    if (!routeEnd || !routeStart) return;
    var distM = getHaversineDistance(routeStart.lat, routeStart.lon, routeEnd.lat, routeEnd.lon);
    var timeMin = Math.round(distM / 83.33 / 60);
    var km = (distM / 1000).toFixed(2);
    var headerEl = document.getElementById('route-result-header');
    var bodyEl = document.getElementById('route-result-body');
    if (headerEl) headerEl.innerHTML = '🚶 <b>~' + timeMin + '分钟</b> <span style="color:#f0883e;font-size:10px">(直线估算)</span>  ' + km + 'km  <span style="color:#6e7681">' + (routeEnd.name || '') + '</span>';
    if (bodyEl) bodyEl.innerHTML = '<div style="color:#8b949e;font-size:11px;padding:8px 0;">💡 启动后端获取精确路线：<br><code style="font-size:10px;background:#161b22;padding:2px 4px;border-radius:3px;">uvicorn routing_api:app --host 0.0.0.0 --port 8765</code></div>';
    var result = document.getElementById('route-result');
    if (result) result.style.display = 'block';
}
async function computeIsochrone() {
    if (!routeStart) { alert('请先在地图上点击设置起点'); return; }
    var loading = document.getElementById('route-loading');
    if (loading) loading.style.display = 'block';
    try {
        var resp = await fetch(ROUTING_API_BASE + '/service-area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lon: routeStart.lon, lat: routeStart.lat, time_min: isochroneTimeMin })
        });
        var data = await resp.json();
        if (isochroneLayer) { map.removeLayer(isochroneLayer); isochroneLayer = null; }
        isochroneLayer = L.layerGroup();
        var timeColor = isochroneTimeMin <= 10 ? '#2ea043' : isochroneTimeMin <= 15 ? '#f0883e' : '#da3633';
        if (data.polygon && data.polygon.length >= 3) {
            var latlngs = data.polygon.map(function(c) { return [c[1], c[0]]; });
            L.polygon(latlngs, {
                color: timeColor, weight: 2,
                opacity: isochroneVisible ? 0.6 : 0,
                fillColor: timeColor,
                fillOpacity: isochroneVisible ? 0.12 : 0,
                dashArray: '6 3',
            }).addTo(isochroneLayer);
        }
        if (data.reachable_edges) {
            data.reachable_edges.forEach(function(edge) {
                var from = data.node_coords ? data.node_coords[edge.u] : null;
                var to = data.node_coords ? data.node_coords[edge.v] : null;
                if (from && to) {
                    L.polyline([[from[1], from[0]], [to[1], to[0]]], {
                        color: timeColor, weight: 3,
                        opacity: isochroneVisible ? 0.4 : 0, fillOpacity: 0,
                    }).addTo(isochroneLayer);
                }
            });
        }
        isochroneLayer.addTo(map);
        var areaKm2 = data.reachable_area_km2 ? data.reachable_area_km2.toFixed(2) : '—';
        var headerEl = document.getElementById('route-result-header');
        var bodyEl = document.getElementById('route-result-body');
        if (headerEl) headerEl.innerHTML = '🕐 <b>' + isochroneTimeMin + '分钟步行等时圈</b>  可达节点: <b>' + (data.reachable_nodes || 0) + '</b>  覆盖: <b>' + areaKm2 + 'km²</b>';
        if (bodyEl) bodyEl.innerHTML = (data.reachable_edges ? '路网边: <b>' + data.reachable_edges.length + '</b> 条' : '') + '<br><span style="color:#6e7681">凸包多边形为可达范围近似</span>';
        var result = document.getElementById('route-result');
        if (result) result.style.display = 'block';
    } catch(e) {
        fallbackIsochroneResult();
    } finally {
        if (loading) loading.style.display = 'none';
    }
}
function fallbackIsochroneResult() {
    if (!routeStart) return;
    var radiusM = isochroneTimeMin * 60 * 1.388;
    if (isochroneLayer) { map.removeLayer(isochroneLayer); isochroneLayer = null; }
    var timeColor = isochroneTimeMin <= 10 ? '#2ea043' : isochroneTimeMin <= 15 ? '#f0883e' : '#da3633';
    isochroneLayer = L.circle([routeStart.lat, routeStart.lon], {
        radius: radiusM, color: timeColor, weight: 2,
        opacity: isochroneVisible ? 0.6 : 0,
        fillColor: timeColor, fillOpacity: isochroneVisible ? 0.1 : 0,
        dashArray: '6 3',
    }).addTo(map);
    var headerEl = document.getElementById('route-result-header');
    var bodyEl = document.getElementById('route-result-body');
    if (headerEl) headerEl.innerHTML = '🕐 <b>' + isochroneTimeMin + '分钟等时圈</b> <span style="color:#f0883e;font-size:10px">(直线估算)</span>  半径约 <b>' + (radiusM/1000).toFixed(1) + 'km</b>';
    if (bodyEl) bodyEl.innerHTML = '<div style="color:#8b949e;font-size:11px;">💡 启动后端获取真实路网等时圈：<br><code style="font-size:10px;background:#161b22;padding:2px 4px;border-radius:3px;">uvicorn routing_api:app --host 0.0.0.0 --port 8765</code></div>';
    var result = document.getElementById('route-result');
    if (result) result.style.display = 'block';
}
function clearAllRoute() {
    if (isochroneLayer) { map.removeLayer(isochroneLayer); isochroneLayer = null; }
    if (routePolyline) { map.removeLayer(routePolyline); routePolyline = null; }
    if (routeStartMarker) { map.removeLayer(routeStartMarker); routeStartMarker = null; }
    if (routeEndMarker) { map.removeLayer(routeEndMarker); routeEndMarker = null; }
    if (closestFacilitiesLayer) { map.removeLayer(closestFacilitiesLayer); closestFacilitiesLayer = null; }
    routeStart = null;
    routeEnd = null;
    updateRouteUI();
    var result = document.getElementById('route-result');
    if (result) result.style.display = 'none';
}
function getHaversineDistance(lat1, lon1, lat2, lon2) {
    var R = 6371000;
    var t1 = lat1 * Math.PI / 180, t2 = lat2 * Math.PI / 180;
    var dt = (lat2 - lat1) * Math.PI / 180;
    var dl = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dt/2) * Math.sin(dt/2) + Math.cos(t1) * Math.cos(t2) * Math.sin(dl/2) * Math.sin(dl/2);
    return R * 2 * Math.asin(Math.sqrt(a));
}

loadBaseThenTraj();
</script>

<style>
/* POI 列表项 */
.poi-list-item {
    padding: 8px 10px;
    border-bottom: 1px solid #21262d;
    cursor: pointer;
    transition: background 0.15s;
}
.poi-list-item:last-child { border-bottom: none; }
.poi-list-item:hover { background: #21262d; }
.poi-list-item:active { background: #30363d; }

.poi-list-row1 {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 3px;
}
.poi-dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
}
.poi-name {
    font-size: 12px;
    color: #e6edf3;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.poi-dist {
    font-size: 11px;
    font-weight: 600;
    flex-shrink: 0;
}

.poi-list-row2 {
    display: flex;
    align-items: center;
    gap: 5px;
    flex-wrap: wrap;
}
.poi-tag {
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 8px;
}
.poi-dir {
    font-size: 10px;
    color: #8b949e;
}
.poi-walk {
    font-size: 10px;
    color: #8b949e;
}
.poi-addr {
    font-size: 10px;
    color: #6e7681;
    margin-top: 2px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* 滚动条 */
#poi-list::-webkit-scrollbar { width: 4px; }
#poi-list::-webkit-scrollbar-track { background: #161b22; }
#poi-list::-webkit-scrollbar-thumb { background: #30363d; border-radius: 2px; }

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

/* ── 路由分析 ─────────────────────────────────────────────── */
#route-result { font-size: 11px; }
.route-result-step {
    padding: 5px 0;
    border-bottom: 1px solid #21262d;
    display: flex;
    gap: 8px;
    align-items: flex-start;
}
.route-result-step:last-child { border-bottom: none; }
.route-step-icon { font-size: 14px; flex-shrink: 0; }
.route-step-info { flex: 1; }
.route-step-name { color: #e6edf3; font-size: 11px; }
.route-step-meta { font-size: 10px; color: #6e7681; margin-top: 1px; }
.isochrone-poly { opacity: 0.25; weight: 2; }
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

    # Step 4: 轨迹（full 模式下自动查找）
    trajectory_data = None
    traj_path = args.trajectory
    if traj_path is None and args.mode == "full":
        traj_candidates = [
            SCRIPT_DIR / "trajectory_output" / "trajectory_preview_20m.csv.csv",
            SCRIPT_DIR / "trajectory_output" / "trajectory_preview_20m.csv",
            SCRIPT_DIR / "trajectory_output" / "trajectory.csv",
        ]
        for p in traj_candidates:
            if p.exists():
                traj_path = str(p)
                break
    if traj_path:
        trajectory_data = load_trajectory(traj_path)

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
