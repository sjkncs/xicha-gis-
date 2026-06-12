# -*- coding: utf-8 -*-
"""
==============================================================================
南山区连续轨迹采样器 — 用于精细粒度3DGS重建
Nanshan District Continuous Trajectory Sampler for Fine-Grained 3DGS Reconstruction

基于 OSM 路网节点 + 建筑楼栋密度分级 连续采样
生成高密度轨迹点，支持批量街景采集 → 3DGS 重建管线

用法:
    # 基本用法：生成南山区全域连续轨迹
    python trajectory_sampler.py --mode full --spacing 10 --output trajectory_full_10m.csv

    # 仅主次干道（快速测试）
    python trajectory_sampler.py --mode major --spacing 20 --output trajectory_major_20m.csv

    # 指定区域（科技园/蛇口/前海）
    python trajectory_sampler.py --mode zone --zone scipark --spacing 5 --output trajectory_scipark_5m.csv

    # 查看南山区各街道统计
    python trajectory_sampler.py --mode stats

依赖:
    pip install numpy pandas shapely scikit-learn
==============================================================================
"""

import os
import sys
import csv
import math
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import unary_union, nearest_points
from scipy.spatial import cKDTree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ============================================================
# 南山区大致边界 (WGS84)
# ============================================================
NANSHAN_BOUNDARY = {
    "min_lon": 113.8500,
    "max_lon": 113.9750,
    "min_lat": 22.4700,
    "max_lat": 22.5700,
}

# 核心兴趣区
ZONES = {
    "scipark": {
        "name": "深圳南山科技园",
        "bounds": (113.9300, 113.9750, 22.5300, 22.5600),
        "desc": "科技园核心区",
    },
    "shekou": {
        "name": "蛇口",
        "bounds": (113.9000, 113.9500, 22.4700, 22.5000),
        "desc": "蛇口老镇+海上世界",
    },
    "qianhai": {
        "name": "前海",
        "bounds": (113.8700, 113.9200, 22.4800, 22.5200),
        "desc": "前海深港合作区",
    },
    "houhai": {
        "name": "后海",
        "bounds": (113.9300, 113.9700, 22.4700, 22.5000),
        "desc": "后海商业中心",
    },
    "nantou": {
        "name": "南头",
        "bounds": (113.8700, 113.9200, 22.5300, 22.5700),
        "desc": "南头古城+同乐",
    },
}

# ============================================================
# 路径配置
# ============================================================
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJ_DIR = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility"

OSM_NODES_PATH = PROJ_DIR / "osm_data" / "nanshan_network_nodes.csv"
BUILDING_GEOJSON = PROJ_DIR / "building_data" / "nanshan_buildings_official.geojson"
OUTPUT_DIR = SCRIPT_DIR / "trajectory_output"


# ============================================================
# Step 1: 加载 OSM 路网节点，构建道路图
# ============================================================
def load_osm_network():
    """
    加载 OSM 路网节点，构建道路网络图
    返回: nodes_df (DataFrame), edges (list of LineString)
    """
    log.info("Step 1: 加载 OSM 路网节点...")

    if not OSM_NODES_PATH.exists():
        log.error(f"路网节点文件不存在: {OSM_NODES_PATH}")
        log.info("  请先从 OSM 下载南山区路网数据")
        return None, []

    nodes_df = pd.read_csv(OSM_NODES_PATH)
    log.info(f"  节点总数: {len(nodes_df):,} 个")

    # 过滤南山区边界
    n_before = len(nodes_df)
    nodes_df = nodes_df[
        (nodes_df["lon"] >= NANSHAN_BOUNDARY["min_lon"])
        & (nodes_df["lon"] <= NANSHAN_BOUNDARY["max_lon"])
        & (nodes_df["lat"] >= NANSHAN_BOUNDARY["min_lat"])
        & (nodes_df["lat"] <= NANSHAN_BOUNDARY["max_lat"])
    ].copy()
    log.info(f"  边界过滤后: {len(nodes_df):,} 个 ({n_before - len(nodes_df):,} 个在区外)")

    if len(nodes_df) == 0:
        log.error("没有找到任何路网节点！")
        return None, []

    return nodes_df, []


def haversine_m(lon1, lat1, lon2, lat2):
    """计算两点间的大圆距离（米）"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_road_edges_from_nodes(nodes_df, max_edge_dist_m=100):
    """
    从节点构建道路边（基于距离连接）
    OSM 路网中，相邻节点通常距离 < 100m
    如果有实际 .shp 线数据，直接读取会更准确
    """
    log.info("Step 2: 从节点构建道路边（距离连接）...")

    coords = nodes_df[["lon", "lat"]].values
    tree = cKDTree(coords)

    edges = []
    edge_count = 0
    total = len(nodes_df)

    for i, (lon, lat) in enumerate(coords):
        if (i + 1) % 10000 == 0:
            log.info(f"  进度: {i+1:,}/{total:,} ({(i+1)/total*100:.1f}%)")

        dists, indices = tree.query([lon, lat], k=6)

        for j in range(1, min(6, len(indices))):
            neighbor_idx = indices[j]
            neighbor = coords[neighbor_idx]
            neighbor_lon, neighbor_lat = neighbor[0], neighbor[1]

            if neighbor_idx == i:
                continue

            dist_m = haversine_m(lon, lat, neighbor_lon, neighbor_lat)

            if dist_m <= max_edge_dist_m:
                edge = LineString([(lon, lat), (neighbor_lon, neighbor_lat)])
                edges.append({
                    "edge_id": edge_count,
                    "start_idx": i,
                    "end_idx": neighbor_idx,
                    "start_lon": float(lon),
                    "start_lat": float(lat),
                    "end_lon": float(neighbor_lon),
                    "end_lat": float(neighbor_lat),
                    "length_m": float(dist_m),
                    "geometry": edge,
                })
                edge_count += 1

    log.info(f"  生成边数: {edge_count:,} 条")

    if edge_count > 0:
        edges_df = pd.DataFrame(edges)
        edges_df = edges_df.drop_duplicates(subset=["start_idx", "end_idx"])
        log.info(f"  去重后: {len(edges_df):,} 条")
        return edges_df

    return pd.DataFrame()


def build_road_edges_from_shp():
    """
    尝试从 SHP 线数据构建道路边（更准确）
    """
    shp_files = list((SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "osm_data").glob("*.shp"))
    if not shp_files:
        log.info("  未找到 SHP 线数据文件，使用节点距离连接")
        return None

    try:
        import geopandas as gpd
        gdf = gpd.read_file(shp_files[0])
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        edges = []
        for idx, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or not geom.is_valid:
                continue

            def extract_segments(g):
                segs = []
                if g.geom_type == "MultiLineString":
                    for part in g.geoms:
                        segs.extend(extract_segments(part))
                elif g.geom_type == "MultiPolygon":
                    for poly in g.geoms:
                        segs.extend(extract_segments(poly))
                elif g.geom_type in ("GeometryCollection", "MultiPoint"):
                    for part in getattr(g, "geoms", []):
                        segs.extend(extract_segments(part))
                elif hasattr(g, "exterior"):
                    coords_list = list(g.exterior.coords)
                    for k in range(len(coords_list) - 1):
                        segs.append((coords_list[k], coords_list[k + 1]))
                elif g.geom_type == "LineString":
                    coords_list = list(g.coords)
                    for k in range(len(coords_list) - 1):
                        segs.append((coords_list[k], coords_list[k + 1]))
                return segs

            segments = extract_segments(geom)
            fclass = str(row.get("highway", row.get("fclass", "unknown")))

            for k, (c1, c2) in enumerate(segments):
                dist_m = haversine_m(c1[0], c1[1], c2[0], c2[1])
                if dist_m < 500 and dist_m > 0.5:
                    edges.append({
                        "edge_id": int(idx) * 1000 + k,
                        "start_lon": float(c1[0]),
                        "start_lat": float(c1[1]),
                        "end_lon": float(c2[0]),
                        "end_lat": float(c2[1]),
                        "length_m": float(dist_m),
                        "geometry": LineString([c1, c2]),
                        "fclass": fclass,
                    })

        if edges:
            log.info(f"  从 SHP 加载: {len(edges):,} 条道路边")
            return pd.DataFrame(edges)
    except Exception as e:
        log.warning(f"  SHP 加载失败: {e}")

    return None


# ============================================================
# Step 3: 沿道路连续采样
# ============================================================
def sample_along_edges(edges_df, spacing_m=10, road_types=None):
    """
    沿每条道路边等间距采样
    spacing_m: 采样间距（米），默认10米
    road_types: 要采样的道路类型列表，如 ["primary", "secondary", "tertiary", "residential"]
    """
    log.info(f"Step 3: 沿道路连续采样（间距 {spacing_m}m）...")

    if edges_df is None or len(edges_df) == 0:
        log.error("无道路边数据，无法采样")
        return []

    # 过滤道路类型
    if road_types:
        if "fclass" in edges_df.columns:
            edges_df = edges_df[edges_df.get("fclass", "").isin(road_types)]
            log.info(f"  道路类型过滤后: {len(edges_df):,} 条")

    all_points = []
    pt_id = 0

    total_edges = len(edges_df)

    for idx, (_, row) in enumerate(edges_df.iterrows()):
        if (idx + 1) % 20000 == 0:
            log.info(f"  采样进度: {idx+1:,}/{total_edges:,} ({(idx+1)/total_edges*100:.1f}%)")

        start = (row["start_lon"], row["start_lat"])
        end = (row["end_lon"], row["end_lat"])
        length_m = row.get("length_m", haversine_m(*start, *end))

        if length_m < 1:  # 跳过过短的边
            continue

        n_points = max(1, int(length_m / spacing_m))

        for k in range(n_points + 1):
            t = k / n_points if n_points > 0 else 0
            lon = start[0] + t * (end[0] - start[0])
            lat = start[1] + t * (end[1] - start[1])

            all_points.append({
                "pt_id": pt_id,
                "lon": round(lon, 7),
                "lat": round(lat, 7),
                "edge_id": row.get("edge_id", idx),
                "t_on_edge": round(t, 3),
                "dist_from_start_m": round(k * spacing_m, 1),
                "edge_length_m": round(length_m, 1),
                "fclass": row.get("fclass", "unknown"),
            })
            pt_id += 1

    log.info(f"  采样点总数: {pt_id:,} 个")
    return all_points


def deduplicate_nearby(points, min_dist_m=5):
    """去除过近的重复采样点"""
    if not points:
        return []

    log.info(f"  去重（最小间距 {min_dist_m}m）...")

    coords = np.array([[p["lon"], p["lat"]] for p in points])
    tree = cKDTree(coords)

    kept = []
    for i, pt in enumerate(points):
        if i == 0:
            kept.append(pt)
            continue

        # 检查最近点距离
        dists, _ = tree.query(coords[i : i + 1], k=2)
        if len(dists) > 1:
            nearest = sorted(dists[0])[1]  # 第二近（最近的是自己）
            lat_m_per_deg = 111000
            lon_m_per_deg = 111000 * math.cos(math.radians(pt["lat"]))
            nearest_dist = nearest * lat_m_per_deg  # 近似
            if nearest_dist >= min_dist_m:
                kept.append(pt)
        else:
            kept.append(pt)

    removed = len(points) - len(kept)
    log.info(f"  去重完成: {len(points):,} → {len(kept):,} (移除 {removed:,})")
    return kept


def filter_by_zone(points, zone_name=None, bounds=None):
    """按区域过滤采样点"""
    if zone_name and zone_name in ZONES:
        b = ZONES[zone_name]["bounds"]
        bounds = b
        log.info(f"  区域: {ZONES[zone_name]['name']}")

    if bounds:
        min_lon, max_lon, min_lat, max_lat = bounds
        filtered = [p for p in points if min_lon <= p["lon"] <= max_lon and min_lat <= p["lat"] <= max_lat]
        log.info(f"  区域过滤: {len(points):,} → {len(filtered):,}")
        return filtered

    return points


def filter_by_road_type(points, include_types=None, exclude_types=None):
    """按道路类型过滤"""
    if not include_types and not exclude_types:
        return points

    include_types = include_types or []
    exclude_types = exclude_types or []

    if include_types:
        filtered = [p for p in points if p.get("fclass", "unknown") in include_types]
        log.info(f"  包含类型 {include_types}: {len(points):,} → {len(filtered):,}")
        return filtered

    if exclude_types:
        filtered = [p for p in points if p.get("fclass", "unknown") not in exclude_types]
        log.info(f"  排除类型 {exclude_types}: {len(points):,} → {len(filtered):,}")
        return filtered

    return points


# ============================================================
# Step 4: 关联建筑密度信息
# ============================================================
def enrich_with_building_density(points):
    """基于最近的楼栋数据估算局部建筑密度"""
    log.info("Step 4: 关联建筑密度...")

    if not BUILDING_GEOJSON.exists():
        log.warning("  楼栋数据不存在，跳过密度关联")
        return points

    try:
        import geopandas as gpd
        bld_gdf = gpd.read_file(BUILDING_GEOJSON)
        bld_coords = np.array(
            [[g.x, g.y] for g in bld_gdf.geometry if g is not None]
        )
        floors = bld_gdf["floors"].fillna(1).values

        if len(bld_coords) == 0:
            log.warning("  楼栋数据为空")
            return points

        tree = cKDTree(bld_coords)

        for pt in points:
            lon, lat = pt["lon"], pt["lat"]
            dists, indices = tree.query([lon, lat], k=5)
            nearest_floors = floors[indices]
            pt["nearby_floors_avg"] = round(float(np.mean(nearest_floors)), 1)
            pt["building_density"] = "high" if np.mean(nearest_floors) > 15 else (
                "medium" if np.mean(nearest_floors) > 5 else "low"
            )

        log.info("  密度关联完成")

    except Exception as e:
        log.warning(f"  密度关联失败: {e}")

    return points


def bearing(lon1, lat1, lon2, lat2):
    """计算方位角（度，正北为0）"""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    theta = math.atan2(x, y)
    return (math.degrees(theta) + 360) % 360


def estimate_heading(pt, prev_pt, next_pt):
    """基于前后点估算朝向"""
    heading = None

    if prev_pt and next_pt:
        heading = bearing(prev_pt["lon"], prev_pt["lat"], next_pt["lon"], next_pt["lat"])
    elif next_pt:
        heading = bearing(pt["lon"], pt["lat"], next_pt["lon"], next_pt["lat"])

    if heading is not None:
        # 简化为四方向
        if 315 <= heading or heading < 45:
            return 0, "N"
        elif 45 <= heading < 135:
            return 90, "E"
        elif 135 <= heading < 225:
            return 180, "S"
        else:
            return 270, "W"

    return 0, "N"


def estimate_building_type(pt):
    """根据周边楼栋估计建筑类型"""
    density = pt.get("building_density", "medium")
    floors_avg = pt.get("nearby_floors_avg", 5)

    if floors_avg >= 30:
        return "HighRise", "超高层"
    elif floors_avg >= 15:
        return "MidHighRise", "高层"
    elif floors_avg >= 5:
        return "MidRise", "多层"
    else:
        return "LowRise", "低层"


# ============================================================
# Step 5: 导出为采集管线兼容格式
# ============================================================
def export_for_collection(points, output_path, heading_enabled=True):
    """
    导出为 full_pipeline.py 兼容的 CSV 格式
    同时生成按 heading 展开的连续序列
    """
    log.info(f"Step 5: 导出采集格式 → {output_path}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # 去除用户输入的扩展名（避免 .csv.csv）
    base_name = Path(output_path).stem
    main_path = OUTPUT_DIR / f"{base_name}.csv"
    with open(main_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "pt_id", "lon", "lat", "edge_id", "t_on_edge",
                "dist_from_start_m", "edge_length_m", "fclass",
                "nearby_floors_avg", "building_density", "urban_form",
                "urban_form_zh", "heading", "heading_label",
            ],
        )
        writer.writeheader()

        for i, pt in enumerate(points):
            prev_pt = points[i - 1] if i > 0 else None
            next_pt = points[i + 1] if i < len(points) - 1 else None

            urban_form, urban_form_zh = estimate_building_type(pt)
            heading, heading_label = estimate_heading(pt, prev_pt, next_pt)

            writer.writerow({
                "pt_id": pt["pt_id"],
                "lon": pt["lon"],
                "lat": pt["lat"],
                "edge_id": pt.get("edge_id", ""),
                "t_on_edge": pt.get("t_on_edge", ""),
                "dist_from_start_m": pt.get("dist_from_start_m", ""),
                "edge_length_m": pt.get("edge_length_m", ""),
                "fclass": pt.get("fclass", "unknown"),
                "nearby_floors_avg": pt.get("nearby_floors_avg", ""),
                "building_density": pt.get("building_density", ""),
                "urban_form": urban_form,
                "urban_form_zh": urban_form_zh,
                "heading": heading if heading_enabled else "",
                "heading_label": heading_label if heading_enabled else "",
            })

    log.info(f"  主轨迹文件: {main_path} ({len(points):,} 行)")

    # 展开文件：每个点 × 4方向 = 更密集的视角覆盖
    if heading_enabled:
        expanded_path = OUTPUT_DIR / f"{base_name}_4dir.csv"
        with open(expanded_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "pt_id", "lon", "lat", "heading", "heading_label",
                    "fclass", "building_density", "urban_form",
                ],
            )
            writer.writeheader()

            for pt in points:
                urban_form, _ = estimate_building_type(pt)
                for heading, label in [(0, "N"), (90, "E"), (180, "S"), (270, "W")]:
                    writer.writerow({
                        "pt_id": pt["pt_id"],
                        "lon": pt["lon"],
                        "lat": pt["lat"],
                        "heading": heading,
                        "heading_label": label,
                        "fclass": pt.get("fclass", "unknown"),
                        "building_density": pt.get("building_density", ""),
                        "urban_form": urban_form,
                    })

        n_expanded = len(points) * 4
        log.info(f"  4方向展开: {expanded_path} ({n_expanded:,} 行)")

    # GeoJSON 可视化文件
    geojson_path = OUTPUT_DIR / f"{base_name}.geojson"
    features = []
    for pt in points:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [pt["lon"], pt["lat"]],
            },
            "properties": {
                "pt_id": pt["pt_id"],
                "fclass": pt.get("fclass", "unknown"),
                "building_density": pt.get("building_density", ""),
                "urban_form": pt.get("urban_form", ""),
            },
        })

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f, ensure_ascii=False)

    log.info(f"  GeoJSON: {geojson_path}")

    return str(main_path)


def print_stats(points):
    """打印统计信息"""
    if not points:
        log.info("无数据")
        return

    log.info("\n" + "=" * 50)
    log.info("轨迹采样统计")
    log.info("=" * 50)
    log.info(f"  总采样点: {len(points):,}")

    # 道路类型分布
    fclass_counts = {}
    for pt in points:
        fc = pt.get("fclass", "unknown")
        fclass_counts[fc] = fclass_counts.get(fc, 0) + 1
    log.info(f"  道路类型分布:")
    for fc, cnt in sorted(fclass_counts.items(), key=lambda x: -x[1])[:10]:
        log.info(f"    {fc}: {cnt:,}")

    # 建筑密度分布
    density_counts = {}
    for pt in points:
        d = pt.get("building_density", "unknown")
        density_counts[d] = density_counts.get(d, 0) + 1
    log.info(f"  建筑密度分布:")
    for d, cnt in sorted(density_counts.items(), key=lambda x: -x[1]):
        log.info(f"    {d}: {cnt:,}")

    # 区域分布（粗略）
    if points:
        lons = [p["lon"] for p in points]
        lats = [p["lat"] for p in points]
        log.info(f"  经度范围: {min(lons):.4f} — {max(lons):.4f}")
        log.info(f"  纬度范围: {min(lats):.4f} — {max(lats):.4f}")

    log.info("=" * 50)


# ============================================================
# 主流程
# ============================================================
def run(args):
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Step 1: 加载路网
    nodes_df, _ = load_osm_network()
    if nodes_df is None:
        log.error("路网加载失败，退出")
        return

    # Step 2: 尝试从SHP加载边，否则用节点构建
    edges_df = build_road_edges_from_shp()
    if edges_df is None:
        edges_df = build_road_edges_from_nodes(nodes_df, max_edge_dist_m=80)

    if edges_df is None or len(edges_df) == 0:
        log.error("无法构建道路边，退出")
        return

    # Step 3: 采样
    points = sample_along_edges(edges_df, spacing_m=args.spacing)

    # Step 4: 去重
    points = deduplicate_nearby(points, min_dist_m=args.spacing * 0.5)

    # Step 5: 过滤
    if args.zone:
        points = filter_by_zone(points, zone_name=args.zone)
    if args.road_types:
        points = filter_by_zone(points)
        points = filter_by_road_type(points, include_types=args.road_types.split(","))

    # Step 6: 密度关联
    points = enrich_with_building_density(points)

    # Step 7: 统计
    print_stats(points)

    # Step 8: 导出
    if args.output and points:
        # 去除扩展名得到 base_name
        base_name = Path(args.output).stem
        export_for_collection(points, args.output, heading_enabled=True)
        log.info(f"\n完成！输出目录: {OUTPUT_DIR}")
        log.info(f"  采集 CSV: trajectory_output/{base_name}.csv")
        log.info(f"  4方向展开: trajectory_output/{base_name}_4dir.csv")
        log.info(f"  GeoJSON: trajectory_output/{base_name}.geojson")
        log.info(f"\n下一步：")
        log.info(f"  python full_pipeline.py --input trajectory_output/{base_name}_4dir.csv")
        log.info(f"  # 或在 3DGS 管线中使用 .geojson 进行 SfM")


def main():
    parser = argparse.ArgumentParser(
        description="南山区连续轨迹采样器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 完整区域，10米间距
  python trajectory_sampler.py --mode full --spacing 10 --output ns_10m

  # 仅科技园，5米间距（高密度重建）
  python trajectory_sampler.py --zone scipark --spacing 5 --output scipark_5m

  # 仅主干道，20米间距
  python trajectory_sampler.py --road-types primary,secondary,tertiary --spacing 20 --output major_roads

  # 查看统计
  python trajectory_sampler.py --mode stats
""",
    )
    parser.add_argument("--mode", default="full", choices=["full", "major", "stats"])
    parser.add_argument("--spacing", type=int, default=10, help="采样间距（米）")
    parser.add_argument("--output", type=str, default="trajectory", help="输出文件名（不含扩展名）")
    parser.add_argument("--zone", type=str, choices=list(ZONES.keys()), help="指定区域")
    parser.add_argument("--road-types", type=str, help="道路类型（逗号分隔，如 primary,secondary）")
    parser.add_argument("--max-edge-m", type=int, default=80, help="最大边长阈值（米）")

    args = parser.parse_args()

    if args.mode == "stats":
        nodes_df, _ = load_osm_network()
        edges_df = build_road_edges_from_shp()
        if edges_df is None:
            edges_df = build_road_edges_from_nodes(nodes_df, max_edge_dist_m=args.max_edge_m)
        if edges_df is not None:
            log.info(f"道路边总数: {len(edges_df):,}")
            if "fclass" in edges_df.columns:
                log.info("道路类型分布:")
                for fc, cnt in edges_df["fclass"].value_counts().head(15).items():
                    log.info(f"  {fc}: {cnt:,}")
            total_length = edges_df["length_m"].sum()
            log.info(f"道路总长: {total_length/1000:.1f} km")
        return

    run(args)


if __name__ == "__main__":
    main()
