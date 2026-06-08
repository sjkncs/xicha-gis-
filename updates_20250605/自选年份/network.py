"""
network.py — Walkable Network Builder & Router for Nanshan District
南山区步行网络构建与路径规划模块

功能 / Features:
    1. Load OSM road network from shp (shapefile)
    2. Filter walkable edges by fclass (道路类型)
    3. Build a NetworkX MultiGraph with time-based edge weights (时间加权)
    4. Snap POI points to nearest network node (POI匹配到最近节点)
    5. Export network JSON + graph pickle (导出网络数据)
    6. Dijkstra shortest path (最短路径)
    7. Service area computation (服务范围计算)
    8. Facility accessibility analysis (设施可达性分析)

Author: Nanshan GIS Project
Date: 2026
"""

import os
import sys
import json
import pickle
import logging
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
from collections import defaultdict
from typing import Optional

# Configure logging / 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================
# Constants / Walkability Model
# ============================================================

# Walkable fclass types from OSM
# 可步行道路类型 (OpenStreetMap fclass)
WALKABLE_FCLASS = {
    'footway', 'path', 'pedestrian', 'living_street',
    'residential', 'unclassified', 'service', 'track',
    'steps', 'corridor',
    'tertiary', 'tertiary_link',
    'secondary', 'secondary_link',
    'primary', 'primary_link',
}

# One-way road types (may need geometry reversal for bidirectional walking)
# 单向道路类型
ONEWAY_KEYWORDS = {
    'primary_link', 'secondary_link', 'tertiary_link',
    'motorway', 'motorway_link'
}

# Speed model (km/h) by road type / 速度模型 (km/h)
SPEED_KMH = {
    'footway': 4.0,
    'path': 3.5,
    'pedestrian': 4.0,
    'steps': 2.5,
    'corridor': 3.0,
    'living_street': 4.0,
    'residential': 4.5,
    'unclassified': 4.0,
    'service': 3.0,
    'track': 3.0,
    'tertiary': 5.0,
    'tertiary_link': 4.0,
    'secondary': 5.0,
    'secondary_link': 4.0,
    'primary': 5.0,
    'primary_link': 4.0,
}
DEFAULT_SPEED = 4.0  # km/h for unknown types

# Cross penalty: add seconds when crossing a road
# 过街惩罚时间 (秒)，如等待红绿灯 ~15-20秒
CROSS_PENALTY_S = 15

# Paths
# 数据路径
SHP_PATH = r"E:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_road_network.shp"
NODES_CSV_PATH = r"E:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_network_nodes.csv"
POI_CSV_PATH = r"E:\xicha gis 智能定位\projects\15min-urban-accessibility\osm_data\nanshan_poi_integrated_v3_wgs84.csv"

# Output directory
OUT_DIR = r"E:\xicha gis 智能定位\自选年份\network_output"

# ============================================================
# Haversine Distance Helper
# ============================================================

def haversine_meters(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """
    Compute the great-circle distance between two points on Earth.
    计算两点之间的大圆距离 (米)
    
    Args:
        lon1, lat1: Longitude and latitude of point 1 (degrees)
        lon2, lat2: Longitude and latitude of point 2 (degrees)
    
    Returns:
        Distance in meters
    """
    R = 6371000  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)

    a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c


def nearest_node(
    lon: float, lat: float,
    kdtree: cKDTree,
    nodes_arr: np.ndarray,
    nodes_ids: list
) -> Optional[int]:
    """Find nearest node to a point using pre-built KDTree. Returns node_id or None."""
    dist, idx = kdtree.query([lon, lat])
    if idx < len(nodes_ids):
        return nodes_ids[idx]
    return None


def compute_walk_time(length_m: float, speed_kmh: float) -> float:
    """
    Compute walking time in seconds.
    计算步行时间 (秒)
    
    Args:
        length_m: Edge length in meters
        speed_kmh: Speed in km/h
    
    Returns:
        Walk time in seconds
    """
    if speed_kmh <= 0:
        speed_kmh = DEFAULT_SPEED
    return (length_m / 1000.0) / speed_kmh * 3600.0


# ============================================================
# Core Graph Builder
# ============================================================

def build_graph_from_shp(shp_path: str, kdtree: Optional[cKDTree] = None,
                          nodes_arr: Optional[np.ndarray] = None,
                          nodes_ids: Optional[list] = None) -> nx.MultiGraph:
    """
    Load OSM shapefile and build a walkable NetworkX MultiGraph.
    从OSM shapefile加载数据并构建可步行NetworkX MultiGraph
    
    - Filters edges by WALKABLE_FCLASS
    - Computes Haversine edge length and walk time
    - Adds edges bidirectionally (unless oneway='yes')
    - Stores metadata: fclass, name, length_m, walk_time_s
    
    Args:
        shp_path: Path to the .shp file
    
    Returns:
        G: NetworkX MultiGraph with time-weighted edges
    """
    logger.info(f"Loading shapefile: {shp_path}")
    
    # Load with geopandas
    gdf = gpd.read_file(shp_path)
    logger.info(f"  Loaded {len(gdf)} rows, columns: {list(gdf.columns)}")
    
    # Ensure CRS is EPSG:4326
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        logger.info(f"  Transforming CRS from {gdf.crs.to_epsg()} to EPSG:4326")
        gdf = gdf.to_crs(epsg=4326)
    
    G = nx.MultiGraph()
    
    skipped_not_walkable = 0
    skipped_no_geom = 0
    skipped_bad_geom = 0
    edges_added = 0
    
    for idx, row in gdf.iterrows():
        fclass = str(row.get('fclass', '')).strip().lower() if pd.notna(row.get('fclass')) else ''

        if fclass not in WALKABLE_FCLASS:
            skipped_not_walkable += 1
            continue

        geom = row.geometry
        if geom is None:
            skipped_no_geom += 1
            continue

        if not isinstance(geom, LineString) or geom.is_empty or len(list(geom.coords)) < 2:
            skipped_bad_geom += 1
            continue

        coords = list(geom.coords)

        # Compute length by summing segments
        total_length = 0.0
        for i in range(len(coords) - 1):
            total_length += haversine_meters(coords[i][0], coords[i][1], coords[i+1][0], coords[i+1][1])

        speed = SPEED_KMH.get(fclass, DEFAULT_SPEED)
        walk_time = compute_walk_time(total_length, speed)

        # Oneway
        oneway_val = row.get('oneway', '')
        if isinstance(oneway_val, bool):
            is_oneway = oneway_val
        elif isinstance(oneway_val, str):
            is_oneway = oneway_val.strip().lower() in ('yes', 'true', '1', 't')
        else:
            is_oneway = False

        # Snap endpoints to nearest nodes
        lon1, lat1 = coords[0][0], coords[0][1]
        lon2, lat2 = coords[-1][0], coords[-1][1]
        node1_id = nearest_node(lon1, lat1, kdtree, nodes_arr, nodes_ids)
        node2_id = nearest_node(lon2, lat2, kdtree, nodes_arr, nodes_ids)

        if node1_id is None or node2_id is None or node1_id == node2_id:
            skipped_bad_geom += 1
            continue

        name = str(row.get('name', '')).strip() if pd.notna(row.get('name')) else ''
        edge_data = {
            'fclass': fclass,
            'name': name,
            'oneway': is_oneway,
            'length_m': round(total_length, 3),
            'walk_time_s': round(walk_time, 3),
        }

        if is_oneway:
            G.add_edge(node1_id, node2_id, **edge_data)
            edges_added += 1
        else:
            G.add_edge(node1_id, node2_id, **edge_data)
            G.add_edge(node2_id, node1_id, **edge_data)
            edges_added += 2
    
    logger.info(f"  Skipped non-walkable: {skipped_not_walkable}")
    logger.info(f"  Skipped no geometry: {skipped_no_geom}")
    logger.info(f"  Skipped bad geometry: {skipped_bad_geom}")
    logger.info(f"  Graph nodes: {G.number_of_nodes()}, edges: {G.number_of_edges()}")
    
    return G


def build_graph_from_csv_nodes(nodes_csv_path: str, edges_csv_path: Optional[str] = None) -> nx.MultiGraph:
    """
    Build NetworkX MultiGraph from CSV node/edge files.
    从CSV节点文件构建步行网络图
    
    This is used as the primary data source since the OSM shp may not always
    be available. The nodes CSV has: node_id, lon, lat
    The edges CSV (if provided) can define connections.
    
    Args:
        nodes_csv_path: Path to nodes CSV with node_id, lon, lat columns
        edges_csv_path: Optional path to edges CSV with u_id, v_id, fclass, length_m columns
    
    Returns:
        G: NetworkX MultiGraph
    """
    logger.info(f"Loading nodes from CSV: {nodes_csv_path}")
    
    nodes_df = pd.read_csv(nodes_csv_path)
    logger.info(f"  Loaded {len(nodes_df)} nodes, columns: {list(nodes_df.columns)}")
    
    # Ensure correct column names
    node_id_col = 'node_id' if 'node_id' in nodes_df.columns else nodes_df.columns[0]
    lon_col = 'lon' if 'lon' in nodes_df.columns else nodes_df.columns[1]
    lat_col = 'lat' if 'lat' in nodes_df.columns else nodes_df.columns[2]
    
    G = nx.MultiGraph()
    
    # Add all nodes
    for _, row in nodes_df.iterrows():
        node_id = int(row[node_id_col])
        lon = float(row[lon_col])
        lat = float(row[lat_col])
        G.add_node(node_id, lon=lon, lat=lat, node_id=node_id)
    
    logger.info(f"  Added {G.number_of_nodes()} nodes to graph")
    
    # If edges CSV is provided, load edges
    if edges_csv_path and os.path.exists(edges_csv_path):
        logger.info(f"Loading edges from CSV: {edges_csv_path}")
        edges_df = pd.read_csv(edges_csv_path)
        logger.info(f"  Loaded {len(edges_df)} edges")
        
        for _, row in edges_df.iterrows():
            u = int(row['u'])
            v = int(row['v'])
            fclass = str(row.get('fclass', 'unclassified')).strip().lower()
            length_m = float(row.get('length_m', 100.0))
            oneway = bool(row.get('oneway', False))
            
            speed = SPEED_KMH.get(fclass, DEFAULT_SPEED)
            walk_time = compute_walk_time(length_m, speed)
            
            edge_data = {
                'fclass': fclass,
                'name': '',
                'oneway': oneway,
                'length_m': round(length_m, 3),
                'walk_time_s': round(walk_time, 3),
            }
            
            G.add_edge(u, v, **edge_data)
            if not oneway:
                G.add_edge(v, u, **edge_data)
    
    logger.info(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    return G


# ============================================================
# KD-Tree Snapping
# ============================================================

def build_kdtree(nodes_df: pd.DataFrame) -> cKDTree:
    """
    Build scipy cKDTree for fast nearest-neighbor queries.
    构建KD树用于快速最近邻查询
    
    Args:
        nodes_df: DataFrame with 'lon' and 'lat' columns
    
    Returns:
        cKDTree fitted on (lon, lat) coordinates
    """
    coords = nodes_df[['lon', 'lat']].values.astype(np.float64)
    return cKDTree(coords)


def snap_point_to_network(
    lon: float,
    lat: float,
    G: nx.MultiGraph,
    nodes_df: pd.DataFrame,
    kdtree: cKDTree
) -> int:
    """
    Snap a geographic point to the nearest network node using KDTree.
    将地理坐标匹配到最近的网络节点
    
    Args:
        lon, lat: Point coordinates
        G: NetworkX graph (used to verify node exists)
        nodes_df: DataFrame with node_id, lon, lat columns
        kdtree: Pre-built cKDTree
    
    Returns:
        node_id of the nearest network node
    """
    dist, idx = kdtree.query([lon, lat])
    nearest_row = nodes_df.iloc[idx]
    return int(nearest_row['node_id'])


# ============================================================
# Dijkstra Routing
# ============================================================

def dijkstra_time(
    G: nx.MultiGraph,
    source_node,
    cost_attr: str = 'walk_time_s'
) -> tuple[dict, dict]:
    """
    Standard Dijkstra shortest path using time as cost.
    基于步行时间的Dijkstra最短路径算法
    
    Args:
        G: NetworkX MultiGraph
        source_node: Starting node
        cost_attr: Edge attribute to use as cost (default: 'walk_time_s')
    
    Returns:
        (distances, predecessors):
            distances: dict[node -> cost in seconds]
            predecessors: dict[node -> previous_node]
    """
    try:
        # NetworkX Dijkstra with predecessor tracking
        distances, predecessors = nx.bidirectional_dijkstra(
            G, source_node, weight=cost_attr
        )
        # bidirectional_dijkstra returns (distances_dict, predecessors_dict)
        return distances, predecessors
    except nx.NetworkXError:
        return {source_node: 0.0}, {}


def dijkstra_reachable(
    G: nx.MultiGraph,
    source_node,
    cost_attr: str = 'walk_time_s'
) -> tuple[dict, dict]:
    """
    Dijkstra returning all reachable nodes and their distances.
    Dijkstra返回所有可达节点及其距离
    
    Uses NetworkX dijkstra_path_lengths for efficiency.
    
    Args:
        G: NetworkX MultiGraph
        source_node: Starting node
        cost_attr: Edge attribute for cost
    
    Returns:
        (distances_dict, paths_dict): distances from source, paths dict
    """
    try:
        distances = dict(nx.single_source_dijkstra_path_length(G, source_node, weight=cost_attr))
        predecessors = {}
        for target in distances:
            if target != source_node:
                try:
                    path = nx.dijkstra_path(G, source_node, target, weight=cost_attr)
                    if len(path) >= 2:
                        predecessors[target] = path[-2]
                except nx.NetworkXNoPath:
                    pass
        return distances, predecessors
    except (nx.NetworkXError, nx.NetworkXNoPath):
        return {source_node: 0.0}, {}


# ============================================================
# Facility & Service Area Analysis
# ============================================================

def find_closest_facilities(
    G: nx.MultiGraph,
    source_node,
    facilities: list[dict],
    cost_attr: str = 'walk_time_s',
    n_per_type: int = 3
) -> list[dict]:
    """
    Find the N closest facilities of each type from a source node.
    查找每个设施类型中最近的N个设施
    
    Args:
        G: NetworkX MultiGraph
        source_node: Origin node
        facilities: List of dicts with {node_id, name, facility_type, lon, lat}
        cost_attr: Edge weight attribute
        n_per_type: Number of closest facilities per type to return
    
    Returns:
        List of {facility_type, name, node_id, walk_time_s, distance_m, lon, lat}
    """
    if source_node not in G:
        logger.warning(f"Source node {source_node} not in graph")
        return []
    
    distances, _ = dijkstra_reachable(G, source_node, cost_attr)
    
    # Group facilities by type
    by_type = defaultdict(list)
    for fac in facilities:
        by_type[fac['facility_type']].append(fac)
    
    results = []
    
    for ftype, fac_list in by_type.items():
        # Sort by walk time
        type_facilities = []
        for fac in fac_list:
            node_id = fac['node_id']
            if node_id in distances:
                dist = distances[node_id]
                # Get distance in meters from time
                # Approximate: use average speed
                avg_speed = 4.0  # km/h
                dist_m = (dist / 3600.0) * avg_speed * 1000.0
                
                type_facilities.append({
                    'facility_type': ftype,
                    'name': fac.get('name', ''),
                    'node_id': node_id,
                    'walk_time_s': round(dist, 2),
                    'distance_m': round(dist_m, 2),
                    'lon': fac.get('lon'),
                    'lat': fac.get('lat'),
                })
        
        # Sort by walk time and take top N
        type_facilities.sort(key=lambda x: x['walk_time_s'])
        results.extend(type_facilities[:n_per_type])
    
    return results


def compute_service_area(
    G: nx.MultiGraph,
    source_node,
    time_threshold_s: float,
    cost_attr: str = 'walk_time_s',
    nodes_df: Optional[pd.DataFrame] = None
) -> tuple[list, list]:
    """
    Compute the walkable service area within a time threshold.
    计算步行时间阈值内的服务范围
    
    Args:
        G: NetworkX MultiGraph
        source_node: Center node of the service area
        time_threshold_s: Time threshold in seconds (e.g. 900 = 15 min)
        cost_attr: Edge weight attribute
        nodes_df: Optional DataFrame with node_id, lon, lat for coordinate lookup
    
    Returns:
        (reachable_nodes_coords, reachable_edges):
            reachable_nodes_coords: list of (lon, lat) tuples
            reachable_edges: list of ((lon1,lat1), (lon2,lat2)) edge coordinates
    """
    distances, _ = dijkstra_reachable(G, source_node, cost_attr)
    
    # Filter nodes within threshold
    reachable_node_ids = [n for n, d in distances.items() if d <= time_threshold_s]
    
    # Get coordinates
    reachable_coords = []
    for node in reachable_node_ids:
        if nodes_df is not None:
            row = nodes_df[nodes_df['node_id'] == node]
            if not row.empty:
                reachable_coords.append((float(row.iloc[0]['lon']), float(row.iloc[0]['lat'])))
        else:
            # Try to get from graph node attributes
            if 'lon' in G.nodes[node] and 'lat' in G.nodes[node]:
                reachable_coords.append((G.nodes[node]['lon'], G.nodes[node]['lat']))
    
    # Find edges fully within service area
    reachable_edges = []
    for u, v, data in G.edges(data=True):
        if u in distances and v in distances:
            # Edge is in service area if both endpoints are reachable
            if distances[u] <= time_threshold_s and distances[v] <= time_threshold_s:
                u_coords = None
                v_coords = None
                
                if nodes_df is not None:
                    row_u = nodes_df[nodes_df['node_id'] == u]
                    row_v = nodes_df[nodes_df['node_id'] == v]
                    if not row_u.empty:
                        u_coords = (float(row_u.iloc[0]['lon']), float(row_u.iloc[0]['lat']))
                    if not row_v.empty:
                        v_coords = (float(row_v.iloc[0]['lon']), float(row_v.iloc[0]['lat']))
                else:
                    if 'lon' in G.nodes[u]:
                        u_coords = (G.nodes[u]['lon'], G.nodes[u]['lat'])
                    if 'lon' in G.nodes[v]:
                        v_coords = (G.nodes[v]['lon'], G.nodes[v]['lat'])
                
                if u_coords and v_coords:
                    reachable_edges.append((u_coords, v_coords))
    
    logger.info(f"Service area from node {source_node}: "
                f"{len(reachable_coords)} nodes, {len(reachable_edges)} edges within "
                f"{time_threshold_s}s ({time_threshold_s/60:.1f} min)")
    
    return reachable_coords, reachable_edges


def find_reachable_within_time(
    G: nx.MultiGraph,
    source_node: int,
    max_time_s: float,
    cost_attr: str = 'walk_time_s'
) -> dict[int, float]:
    """
    Find all nodes reachable within a time budget.
    查找所有在时间预算内可达的节点
    
    Args:
        G: NetworkX graph
        source_node: Source node
        max_time_s: Maximum time in seconds
        cost_attr: Cost attribute
    
    Returns:
        Dict mapping node_id -> travel_time_s for all reachable nodes
    """
    distances, _ = dijkstra_reachable(G, source_node, cost_attr)
    return {n: d for n, d in distances.items() if d <= max_time_s}


def compute_accessibility_score(
    G: nx.MultiGraph,
    source_node: int,
    facilities: list[dict],
    thresholds_min: list[float] = None
) -> dict:
    """
    Compute multi-modal accessibility score from a source node.
    计算多模式可达性得分
    
    Args:
        G: NetworkX graph
        source_node: Source node
        facilities: List of {node_id, facility_type, name, lon, lat}
        thresholds_min: List of time thresholds in minutes [5, 10, 15, 20, 30]
    
    Returns:
        Dict with per-type and overall accessibility metrics
    """
    if thresholds_min is None:
        thresholds_min = [5, 10, 15, 20, 30]
    
    distances, _ = dijkstra_reachable(G, source_node, 'walk_time_s')
    
    # Group by type
    by_type = defaultdict(list)
    for fac in facilities:
        by_type[fac['facility_type']].append(fac)
    
    results = {
        'node_id': source_node,
        'overall': {}
    }
    
    for threshold_min in thresholds_min:
        threshold_s = threshold_min * 60
        reachable_count = sum(
            1 for fac_list in by_type.values()
            for fac in fac_list
            if fac['node_id'] in distances and distances[fac['node_id']] <= threshold_s
        )
        total_facilities = sum(len(fac_list) for fac_list in by_type.values())
        pct = (reachable_count / total_facilities * 100) if total_facilities > 0 else 0
        results['overall'][f'{threshold_min}min'] = {
            'reachable_count': reachable_count,
            'total_count': total_facilities,
            'coverage_pct': round(pct, 2)
        }
    
    # Per type
    for ftype, fac_list in by_type.items():
        results[ftype] = {}
        for threshold_min in thresholds_min:
            threshold_s = threshold_min * 60
            reachable = [fac for fac in fac_list
                        if fac['node_id'] in distances and distances[fac['node_id']] <= threshold_s]
            reachable.sort(key=lambda x: distances[x['node_id']])
            results[ftype][f'{threshold_min}min'] = {
                'reachable_count': len(reachable),
                'total_count': len(fac_list),
                'closest': reachable[0] if reachable else None,
                'coverage_pct': round(len(reachable) / len(fac_list) * 100, 2) if fac_list else 0
            }
    
    return results


# ============================================================
# Main Builder
# ============================================================

def build_network_from_data() -> nx.MultiGraph:
    """
    Main builder: build network from OSM shp + snap POIs.
    主构建函数：从OSM数据构建网络并匹配POI设施点
    
    Steps:
        1. Load OSM shp -> build MultiGraph
        2. Load nodes CSV -> build kdtree
        3. Load POI CSV -> snap each POI to nearest node
        4. Export: network_graph.pkl, network_nodes.json,
                   network_edges.json, facility_locations.json,
                   walkable_stats.json
    
    Returns:
        G: NetworkX MultiGraph
    """
    logger.info("=" * 60)
    logger.info("Starting network build process")
    logger.info("=" * 60)
    
    # Create output directory
    os.makedirs(OUT_DIR, exist_ok=True)
    logger.info(f"Output directory: {OUT_DIR}")
    
    # ========================================
    # Step 1: Load nodes CSV first (needed for kdtree)
    # ========================================
    logger.info("Loading nodes CSV...")
    nodes_df = pd.read_csv(NODES_CSV_PATH)
    col_map = {}
    for c in nodes_df.columns:
        cl = c.strip().lower()
        if cl == 'node_id' or cl == 'nodeid' or cl == 'id':
            col_map[c] = 'node_id'
        elif cl == 'lon' or cl == 'longitude' or cl == 'lng':
            col_map[c] = 'lon'
        elif cl == 'lat' or cl == 'latitude':
            col_map[c] = 'lat'
    nodes_df = nodes_df.rename(columns=col_map)
    logger.info(f"  Nodes CSV: {len(nodes_df)} nodes, cols: {list(nodes_df.columns)}")

    kdtree = build_kdtree(nodes_df)
    nodes_arr = nodes_df[['lon', 'lat']].values.astype(np.float64)
    nodes_ids = nodes_df['node_id'].tolist()
    logger.info(f"  KDTree built for {len(nodes_ids)} nodes")

    # ========================================
    # Step 2: Build graph from shp (with kdtree) or nodes
    # ========================================
    G = None
    if os.path.exists(SHP_PATH):
        try:
            G = build_graph_from_shp(SHP_PATH, kdtree, nodes_arr, nodes_ids)
            logger.info("  Shp graph built with edges")
        except Exception as e:
            logger.warning(f"Failed to load shp: {e}")

    if G is None:
        logger.info("Building empty graph from nodes (no shp graph)")
        G = build_graph_from_csv_nodes(NODES_CSV_PATH)

    # ========================================
    # Step 3: Load POI / facility data
    # ========================================
    logger.info("Loading POI data...")
    poi_df = pd.read_csv(POI_CSV_PATH)
    logger.info(f"  POI CSV: {len(poi_df)} POIs, cols: {list(poi_df.columns)}")
    
    # Build facility list
    facilities = []
    facility_types_seen = set()
    
    for _, row in poi_df.iterrows():
        # Use WGS84 coordinates if available, else GCJ
        lon = row.get('lon') if 'lon' in row else row.get('gcj_lon')
        lat = row.get('lat') if 'lat' in row else row.get('gcj_lat')
        
        if pd.isna(lon) or pd.isna(lat):
            continue
        
        lon = float(lon)
        lat = float(lat)
        name = str(row.get('name', '')) if pd.notna(row.get('name')) else ''
        facility_type = str(row.get('facility_type', '其他')) if pd.notna(row.get('facility_type')) else '其他'
        
        # Snap to nearest node
        node_id = snap_point_to_network(lon, lat, G, nodes_df, kdtree)
        
        fac = {
            'node_id': node_id,
            'name': name,
            'facility_type': facility_type,
            'lon': lon,
            'lat': lat,
        }
        facilities.append(fac)
        facility_types_seen.add(facility_type)
    
    logger.info(f"  Snapped {len(facilities)} POIs to network nodes")
    logger.info(f"  Facility types: {sorted(facility_types_seen)}")
    
    # ========================================
    # Step 4: Export network files
    # ========================================
    logger.info("Exporting network files...")
    
    # 4a. Save graph pickle
    graph_pkl_path = os.path.join(OUT_DIR, 'network_graph.pkl')
    with open(graph_pkl_path, 'wb') as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info(f"  Saved: {graph_pkl_path}")
    
    # 4b. Export nodes JSON
    nodes_json = []
    for node_id, attrs in G.nodes(data=True):
        nodes_json.append({
            'node_id': int(node_id),
            'lon': float(attrs.get('lon', 0)),
            'lat': float(attrs.get('lat', 0)),
        })
    nodes_json_path = os.path.join(OUT_DIR, 'network_nodes.json')
    with open(nodes_json_path, 'w', encoding='utf-8') as f:
        json.dump(nodes_json, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved: {nodes_json_path} ({len(nodes_json)} nodes)")
    
    # 4c. Export edges JSON
    edges_json = []
    for u, v, data in G.edges(data=True):
        edges_json.append({
            'u': int(u),
            'v': int(v),
            'fclass': data.get('fclass', 'unknown'),
            'length_m': data.get('length_m', 0),
            'walk_time_s': data.get('walk_time_s', 0),
            'oneway': data.get('oneway', False),
        })
    edges_json_path = os.path.join(OUT_DIR, 'network_edges.json')
    with open(edges_json_path, 'w', encoding='utf-8') as f:
        json.dump(edges_json, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved: {edges_json_path} ({len(edges_json)} edges)")
    
    # 4d. Export facility locations JSON
    facilities_json_path = os.path.join(OUT_DIR, 'facility_locations.json')
    with open(facilities_json_path, 'w', encoding='utf-8') as f:
        json.dump(facilities, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved: {facilities_json_path} ({len(facilities)} facilities)")
    
    # 4e. Walkable statistics
    by_fclass = defaultdict(int)
    total_edges = G.number_of_edges()
    walkable_edges = 0
    
    for _, _, data in G.edges(data=True):
        fclass = data.get('fclass', 'unknown')
        by_fclass[fclass] += 1
        walkable_edges += 1
    
    stats = {
        'total_nodes': G.number_of_nodes(),
        'total_edges': total_edges,
        'walkable_edges': walkable_edges,
        'by_fclass': dict(by_fclass),
        'facility_types': sorted(list(facility_types_seen)),
        'total_facilities': len(facilities),
    }
    
    stats_json_path = os.path.join(OUT_DIR, 'walkable_stats.json')
    with open(stats_json_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    logger.info(f"  Saved: {stats_json_path}")
    
    logger.info("=" * 60)
    logger.info("Network build complete!")
    logger.info(f"  Nodes: {G.number_of_nodes()}")
    logger.info(f"  Edges: {G.number_of_edges()}")
    logger.info(f"  Facilities: {len(facilities)}")
    logger.info(f"  Output: {OUT_DIR}")
    logger.info("=" * 60)
    
    return G


# ============================================================
# Utility Functions
# ============================================================

def load_network(
    graph_path: Optional[str] = None,
    nodes_path: Optional[str] = None,
    edges_path: Optional[str] = None,
    facilities_path: Optional[str] = None
) -> tuple:
    """
    Load pre-built network data from output files.
    加载预构建的网络数据
    
    Args:
        graph_path: Path to network_graph.pkl
        nodes_path: Path to network_nodes.json
        edges_path: Path to network_edges.json
        facilities_path: Path to facility_locations.json
    
    Returns:
        (G, nodes_df, edges_df, facilities_df, kdtree)
    """
    if graph_path is None:
        graph_path = os.path.join(OUT_DIR, 'network_graph.pkl')
    if nodes_path is None:
        nodes_path = os.path.join(OUT_DIR, 'network_nodes.json')
    if edges_path is None:
        edges_path = os.path.join(OUT_DIR, 'network_edges.json')
    if facilities_path is None:
        facilities_path = os.path.join(OUT_DIR, 'facility_locations.json')
    
    logger.info("Loading pre-built network from disk...")
    
    # Load graph
    with open(graph_path, 'rb') as f:
        G = pickle.load(f)
    logger.info(f"  Loaded graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    
    # Load nodes
    with open(nodes_path, 'r', encoding='utf-8') as f:
        nodes_list = json.load(f)
    nodes_df = pd.DataFrame(nodes_list)
    logger.info(f"  Loaded nodes JSON: {len(nodes_df)} nodes")
    
    # Load edges
    with open(edges_path, 'r', encoding='utf-8') as f:
        edges_list = json.load(f)
    edges_df = pd.DataFrame(edges_list)
    logger.info(f"  Loaded edges JSON: {len(edges_df)} edges")
    
    # Load facilities
    with open(facilities_path, 'r', encoding='utf-8') as f:
        facilities_list = json.load(f)
    facilities_df = pd.DataFrame(facilities_list)
    logger.info(f"  Loaded facilities JSON: {len(facilities_df)} facilities")
    
    # Build kdtree
    kdtree = build_kdtree(nodes_df)
    
    return G, nodes_df, edges_df, facilities_df, kdtree


def get_node_xy(G: nx.MultiGraph, node_id) -> tuple[float, float]:
    """Get (lon, lat) of a node from the graph."""
    attrs = G.nodes[node_id]
    return float(attrs.get('lon', 0)), float(attrs.get('lat', 0))


def network_summary(G: nx.MultiGraph) -> dict:
    """
    Print and return a summary of the network.
    返回网络统计摘要
    """
    by_fclass = defaultdict(int)
    total_length = 0.0
    total_time = 0.0
    
    for _, _, data in G.edges(data=True):
        fclass = data.get('fclass', 'unknown')
        by_fclass[fclass] += 1
        total_length += data.get('length_m', 0)
        total_time += data.get('walk_time_s', 0)
    
    # Per-type stats
    type_stats = {}
    for fclass, count in sorted(by_fclass.items(), key=lambda x: -x[1]):
        type_stats[fclass] = count
    
    summary = {
        'nodes': G.number_of_nodes(),
        'edges': G.number_of_edges(),
        'total_length_m': round(total_length, 2),
        'total_walk_time_h': round(total_time / 3600, 2),
        'avg_edge_length_m': round(total_length / G.number_of_edges(), 2) if G.number_of_edges() > 0 else 0,
        'edges_by_fclass': type_stats,
    }
    
    logger.info("Network Summary:")
    logger.info(f"  Nodes: {summary['nodes']}")
    logger.info(f"  Edges: {summary['edges']}")
    logger.info(f"  Total length: {summary['total_length_m']:.2f} m")
    logger.info(f"  Avg edge length: {summary['avg_edge_length_m']:.2f} m")
    logger.info(f"  Edges by fclass: {type_stats}")
    
    return summary


# ============================================================
# CLI Entry Point
# ============================================================

if __name__ == '__main__':
    logger.info("Nanshan Walkable Network Builder")
    logger.info("南山区步行网络构建工具")
    
    # Build the network
    G = build_network_from_data()
    
    # Print summary
    summary = network_summary(G)
    
    # Demo: find closest facilities from a sample node
    if G.number_of_nodes() > 0:
        sample_node = list(G.nodes())[0]
        logger.info(f"\nDemo: Service area from node {sample_node}")
        
        # 15-min service area
        coords, edges = compute_service_area(G, sample_node, 900)  # 15 min = 900 s
        logger.info(f"  15-min area: {len(coords)} nodes, {len(edges)} edges")
        
        # 5-min service area
        coords_5, edges_5 = compute_service_area(G, sample_node, 300)  # 5 min
        logger.info(f"   5-min area: {len(coords_5)} nodes, {len(edges_5)} edges")
    
    logger.info("\nDone! All output files saved to:")
    logger.info(f"  {OUT_DIR}")
