# -*- coding: utf-8 -*-
"""
路网连通性构建 + GeoJSON 导出
===================================
从南山区 OSM 路网 SHP 文件构建连通 NetworkX 图，
导出为可用于前端可视化（Three.js / Leaflet）的 GeoJSON，
包含道路分类、宽度、颜色、节点连通信息。

输出:
  - connected_network.geojson    → 带拓扑的道路网（GeoJSON LineString）
  - network_nodes.geojson         → 交叉口节点（GeoJSON Point）
  - routing_graph.json            → 路径规划用邻接表
"""
import warnings, sys, io, os, json, time
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import geopandas as gpd
import networkx as nx
from pathlib import Path
from datetime import datetime

np.random.seed(42)

# ============================================================
# 路径配置
# ============================================================
ROOT = Path(r"E:\xicha gis 智能定位\projects\15min-urban-accessibility")
ROAD_DIR = ROOT / "osm_data"
OUT_DIR = ROOT / "city_visualization"
OUT_DIR.mkdir(exist_ok=True)

# 南山区范围
NS = {'west': 113.85, 'east': 114.05, 'south': 22.45, 'north': 22.65}
WALK_SPEED = 83.33  # m/min (5 km/h)

# ============================================================
# 道路分类配色与样式
# ============================================================
# fclass_en → (rgb_hex, weight_px, label_cn, walkable)
ROAD_STYLE = {
    # OSM highway 分类
    'motorway':          ('#e8e8e8', 4, '高速公路',        False),
    'motorway_link':     ('#d0d0d0', 3, '高速连接路',      False),
    'trunk':             ('#f0c040', 3, '主干道',           False),
    'trunk_link':       ('#f0c040', 2, '主干连接',         False),
    'primary':           ('#ffcc44', 3, '一级道路',         True),
    'primary_link':     ('#ffcc44', 2, '一级连接',         True),
    'secondary':         ('#ffeebb', 2, '二级道路',         True),
    'secondary_link':   ('#ffeebb', 2, '二级连接',         True),
    'tertiary':         ('#ffffcc', 1.5, '三级道路',       True),
    'tertiary_link':   ('#ffffcc', 1.5, '三级连接',       True),
    'residential':      ('#f5f5f5', 1, '居住区道路',      True),
    'living_street':    ('#e8e8d0', 1, '生活街道',        True),
    'service':          ('#e0e0e0', 0.8, '服务性道路',    True),
    'pedestrian':       ('#d0d0b0', 1, '步行街',           True),
    'footway':          ('#b0c0a0', 1, '人行道',           True),
    'cycleway':         ('#a0d0a0', 1, '自行车道',         True),
    'steps':            ('#a0a0c0', 0.8, '台阶',           True),
    'path':             ('#c0c0a0', 1, '小径',             True),
    'unclassified':     ('#e8e8e8', 1, '未分类道路',      True),
    'track':            ('#c8b880', 1, '乡村道路',         True),
    'bus_guideway':     ('#e0e0e0', 1, '公交专用',        False),
    # 中文 fclass_cn 回退
    '城市主干路':        ('#ffcc44', 3, '城市主干路',       True),
    '城市次干路':        ('#ffeebb', 2, '城市次干路',       True),
    '城市支路':         ('#ffffcc', 1.5, '城市支路',      True),
    '内部道路':          ('#e0e0e0', 0.8, '内部道路',      True),
    '人行道路':         ('#b0c0a0', 1, '人行道路',        True),
    '居住区道路':       ('#f5f5f5', 1, '居住区道路',      True),
    '服务性道路':       ('#e0e0e0', 0.8, '服务性道路',    True),
    '其它':             ('#d8d8d8', 1, '其它道路',         True),
}

def get_road_style(fclass_en, fclass_cn=''):
    # 优先用英文分类
    key = str(fclass_en).lower().strip()
    if key in ROAD_STYLE:
        return ROAD_STYLE[key]
    # 回退: 匹配中文
    for cn_key in ['城市主干路', '城市次干路', '城市支路', '内部道路', '人行道路', '居住区道路', '服务性道路', '其它']:
        if cn_key in str(fclass_cn):
            return ROAD_STYLE[cn_key]
    # 默认
    return ('#c8c8c8', 1, '未知道路', True)

# ============================================================
# Step 1: 加载路网 SHP
# ============================================================
def load_road_network():
    print("=" * 60)
    print("Step 1: 加载南山区路网")
    print("=" * 60)
    t0 = time.time()

    shp_files = list(ROAD_DIR.glob("nanshan_road_network.shp"))
    if not shp_files:
        raise FileNotFoundError(f"未找到 nanshan_road_network.shp 于 {ROAD_DIR}")
    shp_path = shp_files[0]
    gdf = gpd.read_file(shp_path)
    print(f"  原始数据: {len(gdf):,} 条")
    print(f"  CRS: {gdf.crs}")

    # 转换 WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # 南山区范围过滤
    gdf = gdf.cx[NS['west']:NS['east'], NS['south']:NS['north']].copy()
    gdf = gdf[gdf.geometry.is_valid].reset_index(drop=True)
    print(f"  南山区内: {len(gdf):,} 条")
    print(f"  耗时: {time.time()-t0:.1f}s")

    # 打印道路分类统计
    if 'fclass' in gdf.columns:
        print("\n  道路分类统计:")
        for fc, cnt in gdf['fclass'].value_counts().head(15).items():
            print(f"    {fc}: {cnt:,}")
    elif 'highway' in gdf.columns:
        print("\n  道路分类统计:")
        for fc, cnt in gdf['highway'].value_counts().head(15).items():
            print(f"    {fc}: {cnt:,}")

    return gdf

# ============================================================
# Step 2: 构建连通 NetworkX 图
# ============================================================
def build_connected_graph(gdf):
    print("\n" + "=" * 60)
    print("Step 2: 构建连通 NetworkX 步行网络图")
    print("=" * 60)
    t1 = time.time()

    G = nx.DiGraph()

    # 节点去重映射: (round7_lon, round7_lat) → node_id
    node_map = {}
    nodes_list = []  # node_id → (lon, lat)

    def get_or_create_node(lon, lat):
        key = (round(lon, 7), round(lat, 7))
        if key not in node_map:
            nid = len(node_map)
            node_map[key] = nid
            nodes_list.append((nid, lon, lat))
        return node_map[key]

    def haversine_m(lon1, lat1, lon2, lat2):
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlam = np.radians(lon2 - lon1)
        a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlam / 2) ** 2
        return 2 * 6371000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))

    edge_count = 0
    skipped = 0
    road_edge_records = []  # 用于 GeoJSON 导出

    fclass_col = 'fclass' if 'fclass' in gdf.columns else ('highway' if 'highway' in gdf.columns else None)
    fclass_cn_col = 'fclass_cn' if 'fclass_cn' in gdf.columns else None
    oneway_col = 'oneway' if 'oneway' in gdf.columns else None

    for _, row in gdf.iterrows():
        fclass_en = str(row.get(fclass_col, 'unclassified')) if fclass_col else 'unclassified'
        fclass_cn = str(row.get(fclass_cn_col, '')) if fclass_cn_col else ''
        fc_en_lower = fclass_en.lower().strip()

        # 样式
        color, weight, label_cn, walkable = get_road_style(fclass_en, fclass_cn)

        if not walkable:
            skipped += 1

        # 提取坐标
        geom = row.geometry
        if geom.geom_type == 'LineString':
            coords = list(geom.coords)
        elif geom.geom_type == 'MultiLineString':
            coords = []
            for line in geom.geoms:
                coords.extend(list(line.coords))
        else:
            continue

        if len(coords) < 2:
            continue

        # 步行速度 (根据道路类型)
        if fc_en_lower in ['footway', 'pedestrian', 'steps', 'path']:
            speed = WALK_SPEED * 0.8
        elif fc_en_lower in ['residential', 'living_street', 'service', 'tertiary', 'tertiary_link']:
            speed = WALK_SPEED * 0.85
        elif fc_en_lower in ['secondary', 'secondary_link', 'primary', 'primary_link']:
            speed = WALK_SPEED * 0.8
        elif fc_en_lower in ['trunk', 'trunk_link']:
            speed = WALK_SPEED * 0.6
        else:
            speed = WALK_SPEED * 0.8 if walkable else WALK_SPEED * 0.3

        # 判断单行道
        oneway_raw = str(row.get(oneway_col, 'no')).lower() if oneway_col else 'no'
        is_oneway = oneway_raw in ['yes', 'true', '1', '-1']

        # 逐段建边
        prev_nid = None
        prev_lon, prev_lat = None, None
        road_coords = []

        for lon, lat in coords:
            nid = get_or_create_node(lon, lat)
            road_coords.append([round(lon, 6), round(lat, 6)])

            if prev_nid is not None:
                seg_len = haversine_m(prev_lon, prev_lat, lon, lat)
                if seg_len > 0:
                    tt = seg_len / speed
                    # 正向边
                    G.add_edge(prev_nid, nid,
                        length=float(seg_len),
                        time=float(tt),
                        road_id=int(row.name) if isinstance(row.name, (int, np.integer)) else 0,
                        fclass_en=str(fclass_en),
                        fclass_cn=str(fclass_cn),
                        label_cn=str(label_cn),
                        color=str(color),
                        weight=float(weight),
                        walkable=bool(walkable),
                        is_oneway=bool(is_oneway),
                    )
                    edge_count += 1

                    # 反向边 (单行道只建正向)
                    if not is_oneway:
                        G.add_edge(nid, prev_nid,
                            length=float(seg_len),
                            time=float(tt),
                            road_id=int(row.name) if isinstance(row.name, (int, np.integer)) else 0,
                            fclass_en=str(fclass_en),
                            fclass_cn=str(fclass_cn),
                            label_cn=str(label_cn),
                            color=str(color),
                            weight=float(weight),
                            walkable=bool(walkable),
                            is_oneway=False,
                        )
                        edge_count += 1
                    else:
                        # 单行道反向但步行可通行（人行道）
                        if walkable:
                            G.add_edge(nid, prev_nid,
                                length=float(seg_len),
                                time=float(tt) * 1.2,
                                road_id=int(row.name) if isinstance(row.name, (int, np.integer)) else 0,
                                fclass_en=str(fclass_en),
                                fclass_cn=str(fclass_cn),
                                label_cn=str(label_cn),
                                color=str(color),
                                weight=float(weight),
                                walkable=True,
                                is_oneway=False,
                            )
                            edge_count += 1

            prev_nid = nid
            prev_lon, prev_lat = lon, lat

        # 记录道路段 (去重——每条原始 SHP 记录只记一次)
        if len(road_coords) >= 2:
            road_edge_records.append({
                'coords': road_coords,
                'fclass_en': str(fclass_en),
                'fclass_cn': str(fclass_cn),
                'label_cn': str(label_cn),
                'color': str(color),
                'weight': float(weight),
                'walkable': bool(walkable),
                'is_oneway': bool(is_oneway),
            })

    print(f"  总节点数: {G.number_of_nodes():,} (去重交叉点+端点)")
    print(f"  总边数:   {G.number_of_edges():,} (含双向)")
    print(f"  步行边:  {sum(1 for _, _, d in G.edges(data=True) if d.get('walkable')):,}")
    print(f"  跳过(不可步行): {skipped:,} 条")
    print(f"  耗时: {time.time()-t1:.1f}s")

    return G, nodes_list, road_edge_records

# ============================================================
# Step 3: 导出 GeoJSON
# ============================================================
def export_geojson(G, nodes_list, road_edge_records):
    print("\n" + "=" * 60)
    print("Step 3: 导出 GeoJSON")
    print("=" * 60)
    t2 = time.time()

    # --- 道路层 ---
    road_features = []
    seen_coords = set()
    for rec in road_edge_records:
        coords = rec['coords']
        coord_key = tuple(tuple(c) for c in coords)
        if coord_key in seen_coords:
            continue
        seen_coords.add(coord_key)

        road_features.append({
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coords
            },
            "properties": {
                "type": "road",
                "fclass_en": rec['fclass_en'],
                "fclass_cn": rec['fclass_cn'],
                "label_cn": rec['label_cn'],
                "color": rec['color'],
                "weight": rec['weight'],
                "walkable": rec['walkable'],
                "is_oneway": rec['is_oneway'],
            }
        })

    road_fc = {
        "type": "FeatureCollection",
        "name": "nanshan_connected_roads",
        "generated_at": datetime.now().isoformat(),
        "road_count": len(road_features),
        "features": road_features
    }

    road_path = OUT_DIR / "connected_roads.geojson"
    with open(road_path, "w", encoding="utf-8") as f:
        json.dump(road_fc, f, ensure_ascii=False)
    print(f"  道路 GeoJSON: {road_path} ({len(road_features):,} 条)")

    # --- 节点层 ---
    node_features = []
    for nid, lon, lat in nodes_list:
        deg_in = G.in_degree(nid)
        deg_out = G.out_degree(nid)
        total_deg = G.degree(nid)
        is_junction = total_deg > 2
        is_endpoint = total_deg == 1

        node_features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [round(lon, 6), round(lat, 6)]
            },
            "properties": {
                "node_id": nid,
                "lon": round(lon, 6),
                "lat": round(lat, 6),
                "degree": int(total_deg),
                "in_degree": int(deg_in),
                "out_degree": int(deg_out),
                "is_junction": bool(is_junction),
                "is_endpoint": bool(is_endpoint),
            }
        })

    node_fc = {
        "type": "FeatureCollection",
        "name": "nanshan_network_nodes",
        "generated_at": datetime.now().isoformat(),
        "node_count": len(node_features),
        "features": node_features
    }

    node_path = OUT_DIR / "network_nodes.geojson"
    with open(node_path, "w", encoding="utf-8") as f:
        json.dump(node_fc, f, ensure_ascii=False)
    print(f"  节点 GeoJSON: {node_path} ({len(node_features):,} 个)")

    # --- 路径规划邻接表 ---
    print("\n  构建路径规划邻接表...")
    adjacency = {}
    for u, v, data in G.edges(data=True):
        if u not in adjacency:
            adjacency[u] = {}
        adjacency[u][v] = {
            "length": round(data['length'], 2),
            "time": round(data['time'], 3),
            "fclass": data.get('fclass_en', ''),
            "color": data.get('color', '#c8c8c8'),
            "weight": data.get('weight', 1),
            "walkable": data.get('walkable', True),
        }

    # 导出节点坐标
    node_coords = {nid: {"lon": round(lon, 6), "lat": round(lat, 6)} for nid, lon, lat in nodes_list}

    routing_data = {
        "type": "routing_graph",
        "generated_at": datetime.now().isoformat(),
        "node_count": G.number_of_nodes(),
        "edge_count": G.number_of_edges(),
        "nodes": node_coords,
        "adjacency": adjacency,
    }

    routing_path = OUT_DIR / "routing_graph.json"
    with open(routing_path, "w", encoding="utf-8") as f:
        json.dump(routing_data, f, ensure_ascii=False, indent=0)
    print(f"  路由图 JSON: {routing_path}")
    print(f"  耗时: {time.time()-t2:.1f}s")

    return road_path, node_path, routing_path

# ============================================================
# 主流程
# ============================================================
def main():
    print("\n" + "#" * 60)
    print("# 路网连通性构建 + GeoJSON 导出")
    print("#" * 60)

    gdf = load_road_network()
    G, nodes_list, road_edge_records = build_connected_graph(gdf)
    export_geojson(G, nodes_list, road_edge_records)

    print("\n" + "=" * 60)
    print("生成完成!")
    print("=" * 60)
    print(f"输出目录: {OUT_DIR}")
    for f in sorted(OUT_DIR.iterdir()):
        if f.suffix in ['.geojson', '.json']:
            size_kb = f.stat().st_size / 1024
            print(f"  - {f.name} ({size_kb:.0f} KB)")
    print("\n下一步: 运行 city_25d_generator.py 生成建筑 GeoJSON，")
    print("然后用 city_visualization_3d.html 查看 3D 可视化。")

if __name__ == "__main__":
    main()
