# -*- coding: utf-8 -*-
"""
2.5D 南山区城市底座可视化
路径一：从已有 GeoJSON 点数据生成可交互城市模型

依赖安装 (conda/pip):
  pip install geopandas pyproj shapely py3dtiles numpy
  # 或: conda install -c conda-forge geopandas pyproj shapely

输入:
  - building_data/nanshan_buildings_official.geojson  (4121 栋楼, 含楼层数)
  - osm_data/nanshan_road_network.*                  (路网)
  - data/streetview/integrated_collection/metadata/baidu_streetview_metadata.csv (全景采样点)
  - segmentation_results_v3/seg_results.csv          (VLM 分割结果)

输出:
  1. city_25d.geojson       → CesiumJS / Mapbox 可直接加载
  2. city_tileset/         → 3D Tiles (Cesium ion 或本地服务)
  3. city_heatmap.json     → 步行可达性热力图数据
  4. visualization.html     → 单文件浏览器可视化 (无需服务器)

方法:
  点 → 缓冲(Buffer) → 楼栋面 → 按用途着色 → 拉伸高度
"""
import os
import sys
import json
import csv
import math
import logging
from pathlib import Path
from datetime import datetime

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ============================================================
# 路径配置
# ============================================================
ROOT = Path(r"e:\xicha gis 智能定位\projects\15min-urban-accessibility")
DATA_DIR = ROOT / "building_data"
OSM_DIR = ROOT / "osm_data"
STREETVIEW_DIR = ROOT / "data" / "streetview" / "integrated_collection" / "metadata"
SEG_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3")
OUT_DIR = ROOT / "city_visualization"
OUT_DIR.mkdir(exist_ok=True)

# ============================================================
# 配色方案 (城市形态语义映射)
# ============================================================
USE_TYPE_COLORS = {
    # use_type: (r, g, b, alpha, display_name)
    1: (120, 180, 220, 200, "住宅/residential"),      # 浅蓝
    2: (255, 200, 80, 200, "商业/commercial"),        # 金黄
    3: (200, 100, 220, 200, "办公/office"),           # 紫
    4: (180, 100, 80, 200, "工业/industrial"),        # 橙褐
    5: (80, 160, 100, 200, "文体/public_space"),       # 绿
    6: (220, 80, 80, 200, "医疗/medical"),            # 红
    7: (220, 150, 60, 200, "文化/cultural"),          # 橙
    8: (100, 200, 220, 200, "科教/education"),       # 青
    9: (180, 180, 180, 200, "其他/other"),           # 灰
}

# 建筑高度分级
FLOOR_HEIGHT_M = 3.0  # 默认层高

# ============================================================
# Step 1: 加载楼栋数据
# ============================================================
def load_buildings():
    """加载 GeoJSON 点数据，转换为带属性的 GeoDataFrame"""
    log.info("Step 1: 加载楼栋点数据...")
    geojson_path = DATA_DIR / "nanshan_buildings_official.geojson"
    gdf = gpd.read_file(geojson_path)
    log.info(f"  加载楼栋: {len(gdf)} 个")
    log.info(f"  CRS: {gdf.crs}")

    # 确保是 WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # 解析属性
    gdf["floors"] = pd.to_numeric(gdf.get("floors", 1), errors="coerce").fillna(1).clip(1, 100)
    gdf["height_m"] = gdf["floors"] * FLOOR_HEIGHT_M
    gdf["use_type"] = pd.to_numeric(gdf.get("use_type", 9), errors="coerce").fillna(9).astype(int)

    # 提取 lon/lat
    gdf["lon"] = gdf.geometry.x
    gdf["lat"] = gdf.geometry.y

    # 映射用途名称
    gdf["use_name"] = gdf["use_type"].map(
        lambda x: USE_TYPE_COLORS.get(x, (180, 180, 180, 200, "未知"))[4]
    )

    # 颜色
    def get_color(ut):
        c = USE_TYPE_COLORS.get(ut, (180, 180, 180, 200, "未知"))
        return {"r": c[0], "g": c[1], "b": c[2]}
    gdf["color"] = gdf["use_type"].apply(get_color)

    return gdf


# ============================================================
# Step 2: 点 → 面 (Buffer 缓冲分析)
# ============================================================
def points_to_polygons(gdf, buffer_dist_m=30):
    """
    将楼栋点转为建筑面
    策略: 根据楼层数动态设置缓冲半径
      - 超高层(>30层): 缓冲 40-60m (大型商业/办公)
      - 高层(10-30层): 缓冲 25-40m
      - 多层(4-10层): 缓冲 15-25m
      - 低层(1-3层): 缓冲 8-15m
    """
    log.info(f"Step 2: 点转面 (缓冲分析, 基准半径 {buffer_dist_m}m)...")

    def dynamic_buffer(row):
        floors = row["floors"]
        # 动态半径: 层数越多，楼栋占地面积越大
        if floors >= 30:
            r = buffer_dist_m * 2.0
        elif floors >= 15:
            r = buffer_dist_m * 1.5
        elif floors >= 8:
            r = buffer_dist_m * 1.2
        elif floors >= 4:
            r = buffer_dist_m * 0.9
        else:
            r = buffer_dist_m * 0.6
        return row.geometry.buffer(r / 111000.0, cap_style=1)  # 度转换

    gdf_buffered = gdf.copy()
    gdf_buffered.geometry = gdf_buffered.apply(dynamic_buffer, axis=1)

    # 验证
    valid = gdf_buffered[gdf_buffered.geometry.is_valid]
    invalid = len(gdf_buffered) - len(valid)
    if invalid > 0:
        log.warning(f"  修复 {invalid} 个无效几何")
        gdf_buffered.loc[~gdf_buffered.geometry.is_valid, "geometry"] = (
            gdf_buffered.loc[~gdf_buffered.geometry.is_valid].geometry.buffer(0)
        )

    log.info(f"  面生成完成: {len(gdf_buffered)} 个")
    return gdf_buffered


# ============================================================
# Step 3: 加载全景采样点 (299个位置)
# ============================================================
def load_panorama_points():
    """加载全景采样点作为导航锚点"""
    log.info("Step 3: 加载全景采样点...")

    # 优先用 metadata
    metadata_path = STREETVIEW_DIR / "baidu_streetview_metadata.csv"
    if metadata_path.exists():
        df = pd.read_csv(metadata_path)
        if "longitude" in df.columns and "latitude" in df.columns:
            pts = gpd.GeoDataFrame(
                df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326"
            )
            log.info(f"  全景采样点: {len(pts)} 个 (from metadata)")
            return pts

    # 回退: 从 manifest
    manifest = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\manifest.csv")
    if manifest.exists():
        rows = []
        with open(manifest, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    rows.append({
                        "lng": float(row["lng"]),
                        "lat": float(row["lat"]),
                        "heading": row.get("heading_label", ""),
                        "district": row.get("district", ""),
                        "township": row.get("township", ""),
                        "road_name": row.get("road_name", ""),
                        "urban_form": row.get("urban_form", ""),
                    })
                except (ValueError, KeyError):
                    continue
        df = pd.DataFrame(rows)
        # 去重(同一位置保留一个)
        df = df.drop_duplicates(subset=["lng", "lat"])
        pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.lng, df.lat), crs="EPSG:4326")
        log.info(f"  全景采样点: {len(pts)} 个 (from manifest, 去重后)")
        return pts

    log.warning("  未找到全景采样点数据")
    return None


# ============================================================
# Step 4: 加载分割结果 (语义分析)
# ============================================================
def load_segmentation_results():
    """加载 VLM 分割结果，关联到全景采样点"""
    log.info("Step 4: 加载 VLM 分割结果...")

    seg_path = SEG_DIR / "seg_results.csv"
    if not seg_path.exists():
        log.warning(f"  未找到分割结果: {seg_path}")
        return None

    df = pd.read_csv(seg_path)
    log.info(f"  分割结果: {len(df)} 条")

    # 按 point_key 分组聚合 (4个朝向的平均)
    numeric_cols = ["building_pct", "road_pct", "green_pct", "sky_pct",
                    "openness", "canyon", "density", "walkability"]

    agg_dict = {col: "mean" for col in numeric_cols if col in df.columns}
    agg_dict.update({"township": "first", "urban_form": "first", "lng": "first", "lat": "first"})

    grouped = df.groupby("point_key").agg(agg_dict).reset_index()
    log.info(f"  聚合为: {len(grouped)} 个位置点")

    return grouped


# ============================================================
# Step 5: 加载 OSM 路网
# ============================================================
def load_osm_network():
    """加载 OSM 路网数据"""
    log.info("Step 5: 加载 OSM 路网...")

    shp_files = [f for f in OSM_DIR.glob("nanshan_road_network.*") if f.suffix == ".shp"]
    if shp_files:
        gdf = gpd.read_file(shp_files[0])
        # 转换坐标
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        log.info(f"  路网: {len(gdf)} 条线")
        return gdf

    # 从节点 CSV 重建路网
    nodes_path = OSM_DIR / "nanshan_network_nodes.csv"
    if nodes_path.exists():
        nodes = pd.read_csv(nodes_path)
        log.info(f"  路网节点: {len(nodes)} 个")
        return None

    log.warning("  未找到 OSM 路网数据")
    return None


# ============================================================
# Step 6: 生成 CesiumJS GeoJSON (可直接在浏览器加载)
# ============================================================
def export_cesium_geojson(gdf_buffered, seg_data, panorama_pts, osm_gdf):
    """导出为 CesiumJS / Mapbox 可直接加载的 GeoJSON"""
    log.info("Step 6: 导出 CesiumJS GeoJSON...")

    # ===== Building Layer =====
    features = []

    # Walkability 评分颜色映射
    def walkability_to_color(w):
        """0-10 分 → 冷暖色: 红(差) → 黄(中) → 绿(好)"""
        w = max(0, min(10, w or 5))
        t = w / 10.0
        if t < 0.4:
            r = 255; g = int(120 + 135 * t / 0.4); b = 80
        elif t < 0.7:
            r = int(255 - 255 * (t - 0.4) / 0.3)
            g = int(255 - 135 * (t - 0.4) / 0.3); b = 80
        else:
            r = int(255 * (1 - t) / 0.3); g = 255; b = int(80 + 175 * (t - 0.7) / 0.3)
        return [r, g, b, 200]

    # 分割数据 lookup
    seg_lookup = {}
    if seg_data is not None:
        for _, row in seg_data.iterrows():
            key = f"{row.get('lng', '')}_{row.get('lat', '')}"
            seg_lookup[key] = row

    for _, row in gdf_buffered.iterrows():
        geom = row.geometry
        if not geom.is_valid:
            continue

        coords = []
        if geom.geom_type == "Polygon":
            coords = list(geom.exterior.coords)
        elif geom.geom_type == "MultiPolygon":
            coords = list(geom.geoms[0].exterior.coords)
        else:
            continue

        # 转换坐标顺序: [lon, lat] → GeoJSON 规范 [lon, lat]
        geojson_coords = [[round(c[0], 6), round(c[1], 6)] for c in coords]

        # 高度
        height = float(row.get("height_m", 9 * FLOOR_HEIGHT_M))
        floors = int(row.get("floors", 1))
        use_type = int(row.get("use_type", 9))
        use_name = row.get("use_name", "未知")
        color = row.get("color", {"r": 180, "g": 180, "b": 180})

        # 查找最近的分割结果
        nearest_walkability = None
        try:
            lon, lat = row.get("lon"), row.get("lat")
            key = f"{lon}_{lat}"
            if key in seg_lookup:
                nearest_walkability = seg_lookup[key].get("walkability")
        except Exception:
            pass

        # CesiumJS polygon with height (extruded)
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [geojson_coords]
            },
            "properties": {
                "name": row.get("name", row.get("addr", "")),
                "address": row.get("addr", ""),
                "floors": floors,
                "height_m": round(height, 1),
                "use_type": use_type,
                "use_name": use_name,
                "color_r": color["r"],
                "color_g": color["g"],
                "color_b": color["b"],
                "walkability": round(nearest_walkability, 1) if nearest_walkability else None,
                "walkability_color": walkability_to_color(nearest_walkability) if nearest_walkability else None,
            }
        }
        features.append(feature)

    # ===== Panorama Point Layer =====
    if panorama_pts is not None:
        for _, row in panorama_pts.iterrows():
            try:
                pt = row.geometry
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [round(pt.x, 6), round(pt.y, 6)]
                    },
                    "properties": {
                        "type": "panorama",
                        "heading": row.get("heading", ""),
                        "township": row.get("township", ""),
                        "road_name": row.get("road_name", ""),
                        "urban_form": row.get("urban_form", ""),
                    }
                })
            except Exception:
                continue

    # ===== OSM Network Layer =====
    if osm_gdf is not None:
        for _, row in osm_gdf.iterrows():
            geom = row.geometry
            if geom.geom_type == "LineString":
                coords = [[round(c[0], 6), round(c[1], 6)] for c in geom.coords]
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "type": "road",
                        "fclass": row.get("fclass", row.get("highway", "unknown")),
                    }
                })

    geojson = {
        "type": "FeatureCollection",
        "name": "nanshan_city_25d",
        "generated_at": datetime.now().isoformat(),
        "building_count": len([f for f in features if f["geometry"]["type"] == "Polygon"]),
        "features": features
    }

    out_path = OUT_DIR / "city_cesium.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    log.info(f"  已导出: {out_path} ({len(features)} 个要素)")
    return out_path


# ============================================================
# Step 7: 生成 HTML 单文件可视化 (无需服务器)
# ============================================================
def generate_html_viewer(geojson_path):
    """生成独立的 HTML 文件，直接在浏览器打开即可查看"""
    log.info("Step 7: 生成 HTML 可视化器...")

    html_content = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>南山区 2.5D 城市底座可视化</title>

<!-- Leaflet CSS -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0d1117;
    color: #e6edf3;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

#header {
    background: linear-gradient(135deg, #161b22, #1c2128);
    border-bottom: 1px solid #30363d;
    padding: 12px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-shrink: 0;
    z-index: 1000;
}

#header h1 {
    font-size: 16px;
    font-weight: 600;
    background: linear-gradient(90deg, #58a6ff, #a371f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

#header .stats {
    font-size: 12px;
    color: #8b949e;
}

.mode-toggle {
    display: flex;
    gap: 6px;
}

.mode-btn {
    padding: 4px 12px;
    border: 1px solid #30363d;
    border-radius: 6px;
    background: transparent;
    color: #8b949e;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.2s;
}

.mode-btn:hover { border-color: #58a6ff; color: #58a6ff; }
.mode-btn.active { background: #1f6feb; border-color: #1f6feb; color: white; }

#main {
    display: flex;
    flex: 1;
    overflow: hidden;
}

#sidebar {
    width: 280px;
    background: #161b22;
    border-right: 1px solid #30363d;
    overflow-y: auto;
    flex-shrink: 0;
}

#map {
    flex: 1;
    z-index: 1;
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1117; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }

/* Sidebar sections */
.section {
    border-bottom: 1px solid #21262d;
    padding: 14px;
}

.section-title {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8b949e;
    margin-bottom: 10px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 12px;
    cursor: pointer;
    padding: 3px 6px;
    border-radius: 4px;
    transition: background 0.15s;
}

.legend-item:hover { background: #21262d; }
.legend-item.disabled { opacity: 0.35; }

.legend-color {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    flex-shrink: 0;
}

.legend-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 2px solid;
    flex-shrink: 0;
}

/* Building tooltip */
.building-popup h3 {
    font-size: 14px;
    color: #e6edf3;
    margin-bottom: 6px;
    border-bottom: 1px solid #30363d;
    padding-bottom: 6px;
}

.building-popup .row {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    margin: 4px 0;
    color: #8b949e;
}

.building-popup .row span { color: #e6edf3; }

/* Loading */
#loading {
    position: fixed;
    inset: 0;
    background: #0d1117;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    transition: opacity 0.5s;
}

#loading.hidden { opacity: 0; pointer-events: none; }

.spinner {
    width: 48px;
    height: 48px;
    border: 3px solid #21262d;
    border-top-color: #58a6ff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 16px;
}

@keyframes spin { to { transform: rotate(360deg); } }

#loading p { color: #8b949e; font-size: 14px; }

/* 3D extrude toggle */
#building-info {
    position: absolute;
    bottom: 20px;
    right: 20px;
    background: rgba(22,27,34,0.95);
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 12px 16px;
    z-index: 1000;
    font-size: 12px;
    min-width: 200px;
    backdrop-filter: blur(8px);
}

#building-info h4 { color: #58a6ff; margin-bottom: 6px; font-size: 13px; }
#building-info .info-row { color: #8b949e; margin: 3px 0; }
#building-info .info-row span { color: #e6edf3; float: right; }

/* Search box */
#search-box {
    position: absolute;
    top: 10px;
    right: 10px;
    z-index: 1000;
    display: flex;
    gap: 4px;
}

#search-input {
    padding: 6px 12px;
    border: 1px solid #30363d;
    border-radius: 6px;
    background: rgba(22,27,34,0.95);
    color: #e6edf3;
    font-size: 13px;
    width: 200px;
    outline: none;
    transition: border-color 0.2s;
    backdrop-filter: blur(8px);
}

#search-input:focus { border-color: #58a6ff; }
#search-input::placeholder { color: #484f58; }

#search-btn {
    padding: 6px 12px;
    background: #1f6feb;
    border: none;
    border-radius: 6px;
    color: white;
    cursor: pointer;
    font-size: 12px;
    transition: background 0.2s;
}

#search-btn:hover { background: #388bfd; }

/* Walkability bar */
.walkability-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
}

.walkability-label { font-size: 11px; color: #8b949e; }
.walkability-bar-bg {
    flex: 1;
    height: 6px;
    background: #21262d;
    border-radius: 3px;
    overflow: hidden;
}

.walkability-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.4s ease;
}
</style>
</head>
<body>

<div id="loading">
    <div class="spinner"></div>
    <p>加载南山区城市数据...</p>
</div>

<div id="header">
    <div>
        <h1>南山区 2.5D 城市底座</h1>
        <div class="stats" id="stats-bar">初始化中...</div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
        <div class="mode-toggle">
            <button class="mode-btn active" data-mode="satellite">卫星底图</button>
            <button class="mode-btn" data-mode="dark">深色道路</button>
            <button class="mode-btn" data-mode="streets">街道图</button>
        </div>
        <div class="mode-toggle">
            <button class="mode-btn" data-layer="building">楼栋</button>
            <button class="mode-btn" data-layer="panorama">全景点</button>
            <button class="mode-btn" data-layer="road">路网</button>
            <button class="mode-btn active" data-layer="walkability">可达性</button>
        </div>
    </div>
</div>

<div id="main">
    <div id="sidebar">
        <div class="section">
            <div class="section-title">建筑用途类型</div>
            <div id="use-type-legend"></div>
        </div>

        <div class="section">
            <div class="section-title">步行可达性</div>
            <div style="font-size:11px;color:#8b949e;margin-bottom:8px;">
                0 = 差（红）→ 10 = 好（绿）
            </div>
            <div style="display:flex;gap:8px;align-items:center;">
                <span style="color:#f85149;font-size:11px;">差</span>
                <div style="flex:1;height:8px;background:linear-gradient(90deg,#f85149,#d29922,#56d364);border-radius:4px;"></div>
                <span style="color:#56d364;font-size:11px;">好</span>
            </div>
        </div>

        <div class="section">
            <div class="section-title">建筑统计</div>
            <div id="building-stats"></div>
        </div>

        <div class="section">
            <div class="section-title">点击地图上的楼栋查看详情</div>
        </div>
    </div>

    <div id="map">
        <div id="search-box">
            <input id="search-input" placeholder="搜索楼栋名称 / 地址..." />
            <button id="search-btn">搜索</button>
        </div>
        <div id="building-info" style="display:none;">
            <h4 id="info-name">-</h4>
            <div class="info-row">用途: <span id="info-use">-</span></div>
            <div class="info-row">层数: <span id="info-floors">-</span> 层</div>
            <div class="info-row">高度: <span id="info-height">-</span> m</div>
            <div class="info-row">地址: <span id="info-addr">-</span></div>
            <div id="walkability-section" style="display:none;">
                <div class="walkability-label">步行可达性评分</div>
                <div class="walkability-bar">
                    <div class="walkability-bar-bg">
                        <div class="walkability-bar-fill" id="walkability-fill"></div>
                    </div>
                    <span id="walkability-score" style="color:#e6edf3;font-size:12px;min-width:28px;">-</span>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Leaflet JS -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Leaflet.UseStyle -->
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<script>
// ============================================================
// 地图初始化
// ============================================================
const map = L.map('map', {
    center: [22.53, 113.94],
    zoom: 14,
    zoomControl: true,
    attributionControl: false,
});

// 底图切换
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

// ============================================================
// 颜色映射
// ============================================================
const USE_COLORS = {
    1: '#78b4dc',  // 住宅
    2: '#ffc850',  // 商业
    3: '#c864dc',  // 办公
    4: '#b46450',  // 工业
    5: '#50a064',  // 文体
    6: '#dc5050',  // 医疗
    7: '#dc963c',  // 文化
    8: '#64c8dc',  // 科教
    9: '#b4b4b4',  // 其他
};

function getWalkabilityColor(w) {
    if (w == null) return '#484f58';
    w = Math.max(0, Math.min(10, w));
    const t = w / 10;
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
// 加载 GeoJSON 数据
// ============================================================
let buildingLayer, panoramaLayer, roadLayer;
const layers = { building: null, panorama: null, road: null };
const layerVisibility = { building: true, panorama: true, road: true, walkability: true };

fetch('city_cesium.geojson')
    .then(r => r.json())
    .then(data => {
        // 统计
        const buildings = data.features.filter(f => f.geometry.type === 'Polygon');
        const panoramas = data.features.filter(f => f.geometry.type === 'Point' && f.properties.type === 'panorama');
        const roads = data.features.filter(f => f.geometry.type === 'LineString');

        document.getElementById('stats-bar').textContent =
            `${buildings.length} 栋楼 | ${panoramas.length} 个全景点 | ${roads.length} 条道路`;

        // 建筑统计
        const floors = buildings.map(f => f.properties.floors).filter(f => f);
        if (floors.length > 0) {
            const avgFloors = (floors.reduce((a,b) => a+b, 0) / floors.length).toFixed(1);
            const maxFloors = Math.max(...floors);
            document.getElementById('building-stats').innerHTML = `
                <div class="info-row">平均层数: <span>${avgFloors} 层</span></div>
                <div class="info-row">最高: <span>${maxFloors} 层</span></div>
                <div class="info-row">总数: <span>${buildings.length} 栋</span></div>
            `;
        }

        // 生成图例
        const useTypes = [...new Set(buildings.map(f => f.properties.use_type))];
        const legendDiv = document.getElementById('use-type-legend');
        legendDiv.innerHTML = useTypes.map(ut => {
            const names = {1:'住宅',2:'商业',3:'办公',4:'工业',5:'文体',6:'医疗',7:'文化',8:'科教',9:'其他'};
            const name = names[ut] || ut;
            const color = USE_COLORS[ut] || '#b4b4b4';
            return `<div class="legend-item" data-type="${ut}">
                <div class="legend-color" style="background:${color}"></div>
                <span>${name}</span>
            </div>`;
        }).join('');

        // 图例点击 → 过滤显示
        legendDiv.querySelectorAll('.legend-item').forEach(item => {
            item.addEventListener('click', () => {
                const type = item.dataset.type;
                item.classList.toggle('disabled');
                const disabled = item.classList.contains('disabled');
                if (buildingLayer) {
                    buildingLayer.eachLayer(layer => {
                        const ut = layer.feature.properties.use_type;
                        if (ut == type) {
                            disabled ? map.removeLayer(layer) : map.addLayer(layer);
                        }
                    });
                }
            });
        });

        // 路网层
        if (roads.length > 0) {
            layers.road = L.geoJSON({
                type: 'FeatureCollection',
                features: roads
            }, {
                style: feature => ({
                    color: '#3d444d',
                    weight: feature.properties.fclass === 'primary' ? 3 :
                            feature.properties.fclass === 'secondary' ? 2 : 1,
                    opacity: 0.7,
                }),
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(`道路: ${feature.properties.fclass || 'unknown'}`, {sticky: false});
                }
            });
            if (layerVisibility.road) layers.road.addTo(map);
        }

        // 全景点层
        if (panoramas.length > 0) {
            layers.panorama = L.geoJSON({
                type: 'FeatureCollection',
                features: panoramas
            }, {
                pointToLayer: (feature, latlng) => {
                    return L.circleMarker(latlng, {
                        radius: 5,
                        fillColor: '#a371f7',
                        color: '#8b5cf6',
                        weight: 1.5,
                        fillOpacity: 0.9,
                    });
                },
                onEachFeature: (feature, layer) => {
                    const p = feature.properties;
                    layer.bindTooltip(
                        `📍 全景点<br>${p.township || ''} ${p.road_name || ''}<br>朝向: ${p.heading || ''}`,
                        {sticky: false}
                    );
                }
            });
            if (layerVisibility.panorama) layers.panorama.addTo(map);
        }

        // 建筑层 (按可达性着色)
        buildingLayer = L.geoJSON({
            type: 'FeatureCollection',
            features: buildings
        }, {
            style: feature => {
                const w = feature.properties.walkability;
                const ut = feature.properties.use_type;
                if (layerVisibility.walkability && w != null) {
                    return {
                        fillColor: getWalkabilityColor(w),
                        fillOpacity: 0.75,
                        color: '#ffffff22',
                        weight: 0.5,
                    };
                }
                return {
                    fillColor: USE_COLORS[ut] || '#b4b4b4',
                    fillOpacity: 0.65,
                    color: '#ffffff11',
                    weight: 0.5,
                };
            },
            onEachFeature: (feature, layer) => {
                const p = feature.properties;
                const coords = feature.geometry.coordinates[0];

                // 飞行到该位置
                layer.on('click', () => {
                    const center = L.polygon(coords).getBounds().getCenter();
                    map.flyTo(center, 17, {duration: 1});
                    showBuildingInfo(p);
                });

                // Hover
                layer.on('mouseover', () => {
                    layer.setStyle({ weight: 2, color: '#58a6ff', fillOpacity: 0.9 });
                });
                layer.on('mouseout', () => {
                    layer.setStyle({ weight: 0.5, color: '#ffffff22', fillOpacity: 0.75 });
                });

                // Tooltip
                layer.bindTooltip(
                    `${p.name || p.address || '未知建筑'}<br>` +
                    `${p.use_name || ''} | ${p.floors || '?'}层 | ${p.height_m || '?'}m`,
                    {sticky: false, opacity: 0.9}
                );
            }
        });
        buildingLayer.addTo(map);

        // 搜索功能
        setupSearch(buildings);

        // 隐藏 loading
        document.getElementById('loading').classList.add('hidden');
    })
    .catch(err => {
        document.getElementById('loading').innerHTML =
            `<p style="color:#f85149;">加载失败: ${err.message}</p>
             <p style="color:#8b949e;font-size:12px;margin-top:8px;">
             请确保 city_cesium.geojson 文件与本 HTML 位于同一目录<br>
             并使用本地服务器打开 (python -m http.server 8080)
             </p>`;
    });

// ============================================================
// 建筑信息面板
// ============================================================
function showBuildingInfo(p) {
    const panel = document.getElementById('building-info');
    panel.style.display = 'block';
    document.getElementById('info-name').textContent = p.name || p.address || '未知建筑';
    document.getElementById('info-use').textContent = p.use_name || '未知';
    document.getElementById('info-floors').textContent = p.floors || '-';
    document.getElementById('info-height').textContent = p.height_m ? p.height_m.toFixed(1) : '-';
    document.getElementById('info-addr').textContent = p.address || '-';

    const wSection = document.getElementById('walkability-section');
    const wFill = document.getElementById('walkability-fill');
    const wScore = document.getElementById('walkability-score');
    if (p.walkability != null) {
        wSection.style.display = 'block';
        wFill.style.width = (p.walkability * 10) + '%';
        wFill.style.background = getWalkabilityColor(p.walkability);
        wScore.textContent = p.walkability.toFixed(1);
    } else {
        wSection.style.display = 'none';
    }
}

// ============================================================
// 搜索功能
// ============================================================
function setupSearch(buildings) {
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');

    function doSearch() {
        const q = searchInput.value.trim().toLowerCase();
        if (!q) return;

        const results = buildings.filter(f => {
            const name = (f.properties.name || '').toLowerCase();
            const addr = (f.properties.address || '').toLowerCase();
            return name.includes(q) || addr.includes(q);
        });

        if (results.length > 0) {
            const f = results[0];
            const coords = f.geometry.coordinates[0];
            const center = L.polygon(coords).getBounds().getCenter();
            map.flyTo(center, 18, {duration: 1});
            showBuildingInfo(f.properties);

            // 闪烁效果
            buildingLayer.eachLayer(layer => {
                if (layer.feature === f) {
                    layer.setStyle({ color: '#58a6ff', weight: 3, fillOpacity: 1 });
                    setTimeout(() => layer.setStyle({ color: '#ffffff22', weight: 0.5, fillOpacity: 0.75 }), 2000);
                }
            });
        }
    }

    searchBtn.addEventListener('click', doSearch);
    searchInput.addEventListener('keydown', e => {
        if (e.key === 'Enter') doSearch();
    });
}

// ============================================================
// 图层切换
// ============================================================
document.querySelectorAll('.mode-btn[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn[data-mode]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        map.removeLayer(baseLayers[currentBase]);
        currentBase = btn.dataset.mode;
        baseLayers[currentBase].addTo(map);
    });
});

document.querySelectorAll('.mode-btn[data-layer]').forEach(btn => {
    btn.addEventListener('click', () => {
        const layer = btn.dataset.layer;

        if (['building', 'panorama', 'road'].includes(layer)) {
            btn.classList.toggle('active');
            const visible = btn.classList.contains('active');
            layerVisibility[layer] = visible;

            if (layer === 'building') {
                visible ? buildingLayer.addTo(map) : map.removeLayer(buildingLayer);
            } else if (layer === 'panorama' && layers.panorama) {
                visible ? layers.panorama.addTo(map) : map.removeLayer(layers.panorama);
            } else if (layer === 'road' && layers.road) {
                visible ? layers.road.addTo(map) : map.removeLayer(layers.road);
            }
        } else if (layer === 'walkability') {
            btn.classList.toggle('active');
            layerVisibility.walkability = btn.classList.contains('active');
            if (buildingLayer) {
                buildingLayer.setStyle(feature => {
                    const w = feature.properties.walkability;
                    const ut = feature.properties.use_type;
                    if (layerVisibility.walkability && w != null) {
                        return {
                            fillColor: getWalkabilityColor(w),
                            fillOpacity: 0.75,
                            color: '#ffffff22',
                            weight: 0.5,
                        };
                    }
                    return {
                        fillColor: USE_COLORS[ut] || '#b4b4b4',
                        fillOpacity: 0.65,
                        color: '#ffffff11',
                        weight: 0.5,
                    };
                });
            }
        }
    });
});

// ============================================================
// 比例尺
// ============================================================
L.control.scale({ imperial: false, maxWidth: 150, position: 'bottomright' }).addTo(map);
</script>
</body>
</html>
"""

    html_path = OUT_DIR / "city_visualization.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 同时复制 GeoJSON 到输出目录
    import shutil
    src_geojson = ROOT / "city_cesium.geojson"
    if src_geojson.exists():
        shutil.copy(src_geojson, OUT_DIR / "city_cesium.geojson")

    log.info(f"  HTML 可视化器: {html_path}")
    log.info("  使用方法: python -m http.server 8080 (在输出目录运行), 然后访问 http://localhost:8080")
    return html_path


# ============================================================
# Step 8: 生成热力图数据 (可达性幻觉可视化)
# ============================================================
def generate_walkability_heatmap():
    """生成步行可达性热力图数据，供 Web 可视化使用"""
    log.info("Step 8: 生成可达性热力图数据...")

    seg_path = SEG_DIR / "seg_results.csv"
    if not seg_path.exists():
        log.warning("  无分割结果，跳过热力图")
        return

    df = pd.read_csv(seg_path)

    # 按位置聚合
    agg = df.groupby("point_key").agg({
        "lng": "first", "lat": "first",
        "walkability": "mean",
        "building_pct": "mean",
        "road_pct": "mean",
        "green_pct": "mean",
        "canyon": "mean",
        "openness": "mean",
        "township": "first",
    }).reset_index()

    heatmap_data = []
    for _, row in agg.iterrows():
        if pd.notna(row.get("lng")) and pd.notna(row.get("lat")):
            w = row.get("walkability", 5)
            heatmap_data.append({
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
                "walkability": round(float(w), 2) if pd.notna(w) else 5.0,
                "building_pct": round(float(row.get("building_pct", 0)), 1),
                "road_pct": round(float(row.get("road_pct", 0)), 1),
                "green_pct": round(float(row.get("green_pct", 0)), 1),
                "canyon": round(float(row.get("canyon", 0)), 1),
                "openness": round(float(row.get("openness", 0)), 1),
                "township": row.get("township", ""),
            })

    out_path = OUT_DIR / "walkability_heatmap.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "heatmap", "points": heatmap_data}, f, ensure_ascii=False, indent=2)

    log.info(f"  热力图数据: {out_path} ({len(heatmap_data)} 个点)")

    # 生成各街道统计
    by_twp = agg.groupby("township").agg({
        "walkability": "mean",
        "building_pct": "mean",
        "openness": "mean",
        "canyon": "mean",
    }).round(2)

    stats_path = OUT_DIR / "township_walkability_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        by_twp.to_json(f, force_ascii=False, orient="index")

    log.info(f"  街道统计: {stats_path}")
    return out_path


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("2.5D 南山区城市底座生成器")
    print("=" * 60)

    # 1. 加载楼栋数据
    gdf = load_buildings()

    # 2. 点转面
    gdf_buffered = points_to_polygons(gdf, buffer_dist_m=30)

    # 3. 加载全景采样点
    panorama_pts = load_panorama_points()

    # 4. 加载分割结果
    seg_data = load_segmentation_results()

    # 5. 加载 OSM 路网
    osm_gdf = load_osm_network()

    # 6. 导出 GeoJSON
    export_cesium_geojson(gdf_buffered, seg_data, panorama_pts, osm_gdf)

    # 7. 生成 HTML 可视化器
    html_path = generate_html_viewer(None)

    # 8. 生成热力图
    generate_walkability_heatmap()

    print("\n" + "=" * 60)
    print("生成完成!")
    print(f"输出目录: {OUT_DIR}")
    print("文件清单:")
    for f in OUT_DIR.iterdir():
        size = f.stat().st_size / 1024
        print(f"  - {f.name} ({size:.1f} KB)")
    print("=" * 60)
    print("\n启动可视化:")
    print(f"  cd {OUT_DIR}")
    print("  python -m http.server 8080")
    print("  然后访问 http://localhost:8080/city_visualization.html")
    print("\n依赖安装:")
    print("  pip install geopandas pyproj shapely pandas numpy")


if __name__ == "__main__":
    main()
