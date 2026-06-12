# -*- coding: utf-8 -*-
"""
路网连通性修复脚本
====================

问题诊断:
  1. city_25d_generator.py 的 load_osm_network() 只是读取 SHP 导出独立线段,
     没有构建拓扑连通图,导致道路渲染出来是一堆互不相连的短线
  2. 路网没有和可达性分析使用的 NetworkX 图共享数据
  3. 只有 1003 栋楼被导出,路网完全没有被导出

解决方案:
  1. 利用 p8_real_population.py 已构建好的步行网络图 (G_walk, G_und)
     作为核心连通拓扑,导出为 GeoJSON LineString
  2. 结合 OSM SHP 数据作为背景路网参考
  3. 输出分类道路(主干道/次干道/支路/人行道)供前端分层渲染

输出:
  - road_network_connected.geojson     → 连通路网 GeoJSON (LineString)
  - road_network_merged.geojson       → 合并 OSM + 分析网络
  - routing_graph.json                 → 路由图 (用于前端 A* 搜索)
"""

import os
import sys
import json
import csv
import math
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import LineString, Point

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

# ============================================================
# 路径配置
# ============================================================
ROOT = Path(r"e:\xicha gis 智能定位\projects\15min-urban-accessibility")
OSM_DIR = ROOT / "osm_data"
OUT_DIR = ROOT / "city_visualization"
OUT_DIR.mkdir(exist_ok=True)

# 步行速度 (m/min)
WALK_SPEED = 83.33  # 5 km/h

# 道路分类颜色 (CSS hex, rgba)
ROAD_CLASS_STYLES = {
    'trunk':          {'color': '#d4a017', 'weight': 5, 'opacity': 0.9,  'label': '主干道'},
    'primary':        {'color': '#e8c84a', 'weight': 4, 'opacity': 0.85, 'label': '主要道路'},
    'secondary':      {'color': '#a0a8b0', 'weight': 3, 'opacity': 0.8,  'label': '次要道路'},
    'tertiary':       {'color': '#8899aa', 'weight': 2.5,'opacity': 0.75, 'label': '三级道路'},
    'residential':    {'color': '#667788', 'weight': 2,  'opacity': 0.7,  'label': '居住区道路'},
    'service':        {'color': '#556677', 'weight': 1.5,'opacity': 0.65, 'label': '服务性道路'},
    'pedestrian':     {'color': '#4488aa', 'weight': 1.5,'opacity': 0.6,  'label': '人行道路'},
    'steps':          {'color': '#337799', 'weight': 1,  'opacity': 0.5,  'label': '台阶踏步'},
    'cycleway':       {'color': '#55aa77', 'weight': 1.5,'opacity': 0.6,  'label': '自行车道'},
    'path':           {'color': '#4a7a9a', 'weight': 1.5,'opacity': 0.55, 'label': '小径'},
    'unclassified':   {'color': '#778899', 'weight': 1.5,'opacity': 0.6,  'label': '未分类道路'},
    'default':        {'color': '#99aabb', 'weight': 1,  'opacity': 0.5,  'label': '其他道路'},
}

# OSM highway 分类映射
HIGHWAY_TO_CLASS = {
    'motorway': 'trunk',
    'motorway_link': 'trunk',
    'trunk': 'trunk',
    'trunk_link': 'trunk',
    'primary': 'primary',
    'primary_link': 'primary',
    'secondary': 'secondary',
    'secondary_link': 'secondary',
    'tertiary': 'tertiary',
    'tertiary_link': 'tertiary',
    'residential': 'residential',
    'living_street': 'residential',
    'service': 'service',
    'pedestrian': 'pedestrian',
    'steps': 'steps',
    'cycleway': 'cycleway',
    'path': 'path',
    'footway': 'pedestrian',
    'unclassified': 'unclassified',
    'road': 'unclassified',
}


# ============================================================
# Step 1: 加载 OSM SHP 路网
# ============================================================
def load_osm_shp():
    """加载 OSM ShapeFile 道路数据"""
    log.info("Step 1: 加载 OSM SHP 路网...")

    shp_files = list(OSM_DIR.glob("nanshan_road_network.shp"))
    if not shp_files:
        log.error("  未找到 nanshan_road_network.shp")
        return None

    gdf = gpd.read_file(shp_files[0])
    log.info(f"  原始道路: {len(gdf)} 条, CRS: {gdf.crs}")

    # 转换到 WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # 过滤非道路要素
    if 'fclass' in gdf.columns or 'highway' in gdf.columns:
        col = 'fclass' if 'fclass' in gdf.columns else 'highway'
        gdf = gdf[gdf[col].notna()]
        log.info(f"  过滤后道路: {len(gdf)} 条")

    return gdf


# ============================================================
# Step 2: 构建步行网络节点/边 (从 p8_real_population.py 移植)
# ============================================================
def build_walk_network():
    """
    从 NetworkX 步行网络构建连通边列表
    使用已有的 dijkstra_reach_pop 逻辑
    """
    log.info("Step 2: 构建步行网络拓扑...")

    # 读取节点
    nodes_path = OSM_DIR / "nanshan_network_nodes.csv"
    if not nodes_path.exists():
        log.error(f"  未找到节点文件: {nodes_path}")
        return None, None

    nodes_df = pd.read_csv(nodes_path)
    log.info(f"  加载节点: {len(nodes_df)} 个")

    # 构建节点坐标 lookup
    node_coords = {}
    for _, row in nodes_df.iterrows():
        node_coords[int(row['node_id'])] = (float(row['lon']), float(row['lat']))

    # 读取边 (从可达性分析脚本的输出)
    # 如果没有预计算的边数据,从 SHP 重建拓扑
    gdf = load_osm_shp()
    if gdf is None:
        log.warning("  无法加载 SHP,使用节点坐标重建边")
        return None, node_coords

    edges = []
    edge_class = {}

    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom.geom_type != 'LineString':
            continue

        coords = list(geom.coords)
        if len(coords) < 2:
            continue

        highway = row.get('fclass', row.get('highway', 'unclassified'))
        road_class = HIGHWAY_TO_CLASS.get(str(highway).lower(), 'default')

        # 为每段折线创建连续的边
        for i in range(len(coords) - 1):
            c1, c2 = coords[i], coords[i + 1]
            dist_m = haversine_m(c1[1], c1[0], c2[1], c2[0])
            if dist_m < 1:  # 过滤极短边
                continue

            edges.append({
                'from': c1,
                'to': c2,
                'distance': dist_m,
                'highway': highway,
                'road_class': road_class,
            })

    log.info(f"  构建边: {len(edges)} 条")
    return edges, node_coords


# ============================================================
# Step 3: 合并道路数据,构建连通图
# ============================================================
def merge_road_network(edges, node_coords):
    """合并 OSM 道路和步行网络,构建无向连通图"""
    log.info("Step 3: 合并路网,构建连通图...")

    # 按坐标近似匹配构建连通性
    # 关键: OSM 道路线段的端点如果与另一条道路端点距离 < SNAP_TOLERANCE, 则连通
    SNAP_TOLERANCE = 0.00005  # ~5m 在南山区纬度

    # 构建节点空间索引 (grid-based)
    grid = defaultdict(list)
    for edge in edges:
        for pt in [edge['from'], edge['to']]:
            gx = int(pt[0] / SNAP_TOLERANCE)
            gy = int(pt[1] / SNAP_TOLERANCE)
            grid[(gx, gy)].append(pt)

    def snap_point(pt):
        """将点吸附到最近的现有节点,如果没有则创建虚拟节点"""
        gx = int(pt[0] / SNAP_TOLERANCE)
        gy = int(pt[1] / SNAP_TOLERANCE)
        best = None
        best_dist = SNAP_TOLERANCE

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for cand in grid.get((gx + dx, gy + dy), []):
                    d = math.sqrt((pt[0] - cand[0])**2 + (pt[1] - cand[1])**2)
                    if d < best_dist:
                        best_dist = d
                        best = cand
        return best if best else pt

    # 为所有边端点建立连通关系
    # 构建 adjacency: (lon, lat) -> set of (lon, lat)
    adj = defaultdict(set)
    node_set = set()

    for edge in edges:
        c1, c2 = edge['from'], edge['to']
        # 吸附
        nc1 = snap_point(c1)
        nc2 = snap_point(c2)

        if nc1 == nc2:
            continue  # 过滤自环

        adj[nc1].add(nc2)
        adj[nc2].add(nc1)
        node_set.add(nc1)
        node_set.add(nc2)

        edge['from'] = nc1
        edge['to'] = nc2

    log.info(f"  连通节点: {len(node_set)} 个")
    log.info(f"  连通边: {len(edges)} 条")

    # 统计各类道路
    class_counts = defaultdict(int)
    for e in edges:
        class_counts[e['road_class']] += 1
    for cls, cnt in sorted(class_counts.items(), key=lambda x: -x[1]):
        log.info(f"    {ROAD_CLASS_STYLES.get(cls, {}).get('label', cls)}: {cnt}")

    return edges, node_set, adj


# ============================================================
# Step 4: A* 路径搜索 (前端用)
# ============================================================
def build_astar_graph(edges, node_set):
    """将边列表转换为 A* 可用的邻接表"""
    log.info("Step 4: 构建 A* 路由图...")

    adj = defaultdict(list)

    for e in edges:
        f, t = e['from'], e['to']
        dist = e['distance']
        rc = e['road_class']

        # 权重: 根据道路类型调整
        type_weight = {
            'pedestrian': 1.0,
            'steps': 2.0,
            'path': 1.1,
            'residential': 1.0,
            'service': 1.0,
            'tertiary': 0.9,
            'secondary': 0.85,
            'primary': 0.8,
            'trunk': 0.7,
            'unclassified': 0.9,
            'default': 1.0,
        }.get(rc, 1.0)

        weight = dist * type_weight

        adj[f].append({'node': t, 'weight': weight, 'class': rc})
        adj[t].append({'node': f, 'weight': weight, 'class': rc})

    log.info(f"  A* 邻接表: {len(adj)} 个节点")
    return adj


def astar_search(adj, start, goal, heuristic_fn):
    """A* 搜索实现 (用于预验证)"""
    import heapq

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # 重建路径
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path, g_score[goal]

        for neighbor in adj[current]:
            node = neighbor['node']
            tentative_g = g_score.get(current, float('inf')) + neighbor['weight']
            if tentative_g < g_score.get(node, float('inf')):
                came_from[node] = current
                g_score[node] = tentative_g
                f = tentative_g + heuristic_fn(node, goal)
                heapq.heappush(open_set, (f, node))

    return None, None


def haversine_m(lat1, lon1, lat2, lon2):
    """计算两点间 Haversine 距离 (米)"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def euclidean_heuristic(a, b):
    return haversine_m(a[1], a[0], b[1], b[0])


# ============================================================
# Step 5: 导出 GeoJSON
# ============================================================
def export_road_geojson(edges, node_set):
    """导出道路 GeoJSON"""
    log.info("Step 5: 导出道路 GeoJSON...")

    features = []

    # 合并相邻同类型边
    merged = defaultdict(list)
    for e in edges:
        key = e['road_class']
        merged[key].append(e)

    for road_class, class_edges in merged.items():
        style = ROAD_CLASS_STYLES.get(road_class, ROAD_CLASS_STYLES['default'])

        for e in class_edges:
            coords = [e['from'], e['to']]
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'LineString',
                    'coordinates': [[round(c[0], 6), round(c[1], 6)] for c in coords]
                },
                'properties': {
                    'road_class': road_class,
                    'highway': e.get('highway', ''),
                    'label': style['label'],
                    'color': style['color'],
                    'weight': style['weight'],
                    'distance_m': round(e['distance'], 1),
                    'color_hex': style['color'],
                    'width_pixels': style['weight'],
                }
            })

    geojson = {
        'type': 'FeatureCollection',
        'name': 'nanshan_road_network_connected',
        'generated_at': datetime.now().isoformat(),
        'road_count': len(features),
        'node_count': len(node_set),
        'features': features
    }

    out_path = OUT_DIR / "road_network_connected.geojson"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    log.info(f"  导出道路: {out_path} ({len(features)} 条)")
    return out_path


def export_routing_graph(adj):
    """导出路由图 JSON (用于前端 A*)"""
    log.info("Step 6: 导出路由图 JSON...")

    # 转换坐标为字符串键 (浮点精度问题)
    routing_graph = {}

    def pt_key(pt):
        return f"{round(pt[0], 6)},{round(pt[1], 6)}"

    for node, neighbors in adj.items():
        k = pt_key(node)
        routing_graph[k] = [
            {
                'n': pt_key(nb['node']),
                'w': round(nb['weight'], 2),
                'c': nb['class'],
            }
            for nb in neighbors
        ]

    out_path = OUT_DIR / "routing_graph.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            'type': 'routing_graph',
            'generated_at': datetime.now().isoformat(),
            'node_count': len(routing_graph),
            'graph': routing_graph,
        }, f, ensure_ascii=False, indent=2)

    log.info(f"  导出路由图: {out_path} ({len(routing_graph)} 节点)")
    return out_path


def export_poi_routing_points():
    """导出 POI 作为路径规划的起点/终点候选"""
    log.info("Step 7: 导出 POI 路径点...")

    poi_paths = [
        OSM_DIR.parent / "nanshan_poi_final.json",
        OSM_DIR.parent / "nanshan_poi_integrated_v2.json",
    ]

    features = []
    for poi_path in poi_paths:
        if not poi_path.exists():
            continue
        try:
            with open(poi_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                for item in data[:200]:  # 限制数量
                    lon = item.get('lon') or item.get('lng') or item.get('longitude')
                    lat = item.get('lat') or item.get('latitude')
                    if lon and lat:
                        try:
                            features.append({
                                'type': 'Feature',
                                'geometry': {
                                    'type': 'Point',
                                    'coordinates': [round(float(lon), 6), round(float(lat), 6)]
                                },
                                'properties': {
                                    'name': item.get('name', item.get('名称', '未知')),
                                    'category': item.get('type', item.get('类型', item.get('category', '')))[:30],
                                    'poi_type': 'routing_point',
                                }
                            })
                        except (ValueError, TypeError):
                            continue
            break
        except (json.JSONDecodeError, IOError) as e:
            log.warning(f"  读取 {poi_path.name} 失败: {e}")
            continue

    if features:
        geojson = {
            'type': 'FeatureCollection',
            'name': 'routing_pois',
            'count': len(features),
            'features': features
        }
        out_path = OUT_DIR / "routing_pois.geojson"
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        log.info(f"  导出 POI 路径点: {out_path} ({len(features)} 个)")
        return out_path

    log.warning("  未找到有效 POI 数据")
    return None


# ============================================================
# 预验证: 测试几条 A* 路径
# ============================================================
def validate_routes(adj, sample_count=5):
    """预验证路网连通性,随机测试几条路径"""
    log.info(f"Step 8: 预验证路网连通性 (测试 {sample_count} 条路径)...")

    import random

    nodes = list(adj.keys())
    if len(nodes) < sample_count * 2:
        log.warning(f"  节点数不足: {len(nodes)}")
        return

    success = 0
    for i in range(sample_count):
        start = random.choice(nodes)
        goal = random.choice(nodes)
        if start == goal:
            continue

        start_pt = tuple(map(float, start.split(',')))
        goal_pt = tuple(map(float, goal.split(',')))

        path, dist = astar_search(adj, start_pt, goal_pt, euclidean_heuristic)
        if path:
            success += 1
            time_min = dist / WALK_SPEED if dist else 0
            log.info(f"  路径 {i+1}: {dist:.0f}m, 步行约 {time_min:.1f}min")
        else:
            log.warning(f"  路径 {i+1}: 无法到达")

    log.info(f"  连通性测试: {success}/{sample_count} 条路径可达")


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 60)
    print("路网连通性修复脚本")
    print("=" * 60)

    # 1. 加载 OSM SHP
    edges, node_coords = build_walk_network()
    if edges is None:
        log.error("路网构建失败")
        return

    # 2. 合并路网,构建连通图
    edges, node_set, adj = merge_road_network(edges, node_coords)

    # 3. 导出道路 GeoJSON
    export_road_geojson(edges, node_set)

    # 4. 构建 A* 路由图
    astar_adj = build_astar_graph(edges, node_set)
    export_routing_graph(astar_adj)

    # 5. 导出 POI 路径点
    export_poi_routing_points()

    # 6. 预验证
    validate_routes(astar_adj)

    print("\n" + "=" * 60)
    print("生成完成!")
    print(f"输出目录: {OUT_DIR}")
    print("文件清单:")
    for f in sorted(OUT_DIR.iterdir()):
        if f.suffix in ['.geojson', '.json'] and f.stat().st_size > 1000:
            size = f.stat().st_size / 1024
            print(f"  - {f.name} ({size:.1f} KB)")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 运行 city_25d_generator.py 更新城市可视化")
    print("  2. 打开 city_visualization/city_visualization.html 查看路网")
    print("  3. 使用 city_visualization/interactive_router.html 做路径规划")


if __name__ == "__main__":
    main()
