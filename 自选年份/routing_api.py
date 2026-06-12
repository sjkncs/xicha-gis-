"""
routing_api.py — 南山区步行可达性路由分析 FastAPI 服务

功能：
    - POST /api/snap: 坐标吸附到最近路网节点
    - POST /api/route: 两点间步行路线规划（时间加权 Dijkstra，异步+缓存）
    - POST /api/closest-facilities: 最近设施查找（按类型）
    - POST /api/service-area: 等时圈计算（路网可达范围）
    - POST /api/living-circle: 15分钟生活圈分析
    - GET  /api/living-circle/facilities: 可达设施列表
    - GET  /api/coverage-grid: 网格化可达性分析
    - GET  /api/facilities: 设施列表（分页+搜索）
    - GET  /api/transit/stations: 交通站点（地铁/公交细分）
    - GET  /api/transit/nearby: 附近交通站点
    - GET  /api/stats: 路网统计
    - GET  /api/transit/realtime/subway: 最近地铁站实时到站信息
    - GET  /api/transit/realtime/bus: 附近公交站实时到站信息
    - GET  /api/transit/realtime/route/{line_id}: 地铁线路实时状态
    - GET  /api/transit/realtime/combined: 综合交通出行分析

部署： Nginx 反代 /api/* → :8765（FastAPI）
启动：
    uvicorn routing_api:app --host 0.0.0.0 --port 8765

依赖：
    pip install fastapi uvicorn[standard] networkx numpy scipy
"""

import os
import json
import pickle
import heapq
import logging
import asyncio
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import numpy as np
from scipy.spatial import cKDTree
import networkx as nx
import math


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters."""
    R = 6371000
    d = math.radians(lat2 - lat1)
    d2 = math.radians(lon2 - lon1)
    a = math.sin(d/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d2/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# 导入实时交通模块
from transit_realtime import (
    get_nearest_subway_station,
    get_nearest_bus_stops,
    get_subway_line_status,
    get_combined_transit_analysis,
    get_all_metro_lines,
    get_all_bus_routes,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Async Worker Pool ─────────────────────────────────────────────
_executor = ThreadPoolExecutor(max_workers=4)
_ROUTE_CACHE: Dict[tuple, Dict] = {}
_ROUTE_CACHE_MAX = 10000
_ROUTE_TIMEOUT_S = 8.0

# ── Paths ───────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
OUT_DIR = SCRIPT_DIR / "network_output"
GRAPH_PATH = OUT_DIR / "network_graph.pkl"
NODES_PATH = OUT_DIR / "network_nodes.json"
FACILITIES_PATH = OUT_DIR / "facility_locations.json"
EDGES_PATH = OUT_DIR / "network_edges.json"

# ── FastAPI App ────────────────────────────────────────────────────
app = FastAPI(
    title="南山区步行可达性路由分析服务",
    version="1.0.0",
    description="路网时间加权等时圈 + 最近设施 + 路线规划",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 中文→英文 设施类型映射 ─────────────────────────────────────
# API 统一返回英文 key，便于前端 FACILITY_NAMES_JS 对齐
FTYPE_CN_TO_EN = {
    # 购物
    "购物服务": "shopping",
    "购物消费": "shopping",
    # 餐饮
    "餐饮服务": "restaurant",
    "餐饮美食": "restaurant",
    # 教育
    "教育培训": "school",
    "科教文化": "school",
    # 医疗
    "医疗保健": "hospital",
    # 交通（统一归 transit，后端按 transit_subtype 细分）
    "交通设施": "transit",
    # 公共
    "公共设施": "public",
    # 企业
    "公司企业": "company",
    # 政府
    "政府机构": "government",
    # 商务
    "商务写字楼": "office",
    # 住宿/酒店
    "住宿服务": "hotel",
    "酒店住宿": "hotel",
    # 生活
    "生活服务": "life",
    # 休闲
    "休闲娱乐": "entertainment",
    # 汽车
    "汽车相关": "car",
    # 运动
    "运动健身": "sports",
    # 金融
    "金融机构": "bank",
    # 旅游
    "旅游景点": "tourism",
    # 其他
    "其他": "other",
}

# ── 交通精细分类（transit 子类型）──────────────────────────────
# 解决"地铁站旁商店被误标为地铁站"问题
TRANSIT_SUBTYPE_RULES = {
    "subway": {
        "keywords": ["地铁站", "地铁出入口", "地铁换乘站", "地铁口", "地铁线路", "subway", "metro station", "M站"],
        "exclude": ["商店", "便利店", "小吃", "餐饮", "咖啡", "奶茶", "快餐", "餐厅", "饭馆", "药房", "药店", "银行", "ATM", "超市", "便利店"],
        "base_score": 0.95,
    },
    "bus": {
        "keywords": ["公交站", "公交中途站", "公交总站", "巴士站", "bus stop", "公交"],
        "exclude": ["商店", "便利店", "小吃", "快餐", "药店", "超市", "便利店"],
        "base_score": 0.85,
    },
    "railway": {
        "keywords": ["火车站", "高铁站", "城际火车站", "railway station", "train station"],
        "exclude": ["商店", "便利店", "小吃", "快餐"],
        "base_score": 0.90,
    },
    "ferry": {
        "keywords": ["渡口", "码头", "轮渡站", "ferry", "port"],
        "exclude": [],
        "base_score": 0.90,
    },
    "taxi": {
        "keywords": ["出租车扬招", "打车点", "taxi stand", "的士站"],
        "exclude": [],
        "base_score": 0.80,
    },
    "parking": {
        "keywords": ["停车场", "停车楼", "P+R", "parking"],
        "exclude": [],
        "base_score": 0.85,
    },
}

# 用于POI名称置信度评分
EXCLUDE_KEYWORDS_SUBWAY = ["商店", "便利店", "小吃", "餐饮", "咖啡", "奶茶", "快餐", "餐厅", "饭馆", "药房", "药店", "银行", "ATM", "超市", "收发室", "传达室", "物业管理", "服务中心", "社区", "警务室"]


def classify_transit_subtype(name: str, category1: str = "", category2: str = "") -> str:
    """
    根据POI名称和分类判断具体交通子类型（subway/bus/railway等）。
    优先用关键词精确匹配，排除干扰词。
    """
    text = f"{name} {category1} {category2}".lower()

    for subtype, rules in TRANSIT_SUBTYPE_RULES.items():
        # 必须包含关键词
        has_keyword = any(k.lower() in text for k in rules["keywords"])
        if not has_keyword:
            continue
        # 不能包含排除词
        has_exclude = any(ex.lower() in text for ex in rules["exclude"])
        if has_exclude:
            continue
        return subtype

    return "other"


def calculate_poi_confidence(name: str, ftype: str,
                           category1: str = "", category2: str = "",
                           distance_to_known_transit: float = None) -> float:
    """
    评估 POI 分类置信度（0.0 ~ 1.0）。
    规则：
    1. 交通设施 transit：检查是否为真正的地铁站（排除"地铁站旁商店"）
    2. 其他设施：基础分 + 距离加权
    """
    base = 0.5

    if ftype == "transit":
        # 交通设施需要进一步细分
        subtype = classify_transit_subtype(name, category1, category2)
        if subtype == "subway":
            # 真正的地铁站 - 检查是否含干扰词
            text = f"{name} {category1} {category2}"
            if any(ex in text for ex in EXCLUDE_KEYWORDS_SUBWAY):
                return 0.15  # 降权极低
            return 0.95
        elif subtype == "bus":
            return 0.85
        elif subtype == "railway":
            return 0.90
        else:
            # 不是已知的交通子类型，降权
            return 0.3

    # 距离已知交通站点的加权
    if distance_to_known_transit is not None:
        if distance_to_known_transit < 30:
            base += 0.35
        elif distance_to_known_transit < 80:
            base += 0.25
        elif distance_to_known_transit < 150:
            base += 0.15
        elif distance_to_known_transit < 300:
            base += 0.05

    return min(base, 1.0)


def normalize_ftype(cn: str) -> str:
    """将中文 facility_type 规范化为英文 key。"""
    return FTYPE_CN_TO_EN.get(cn, "other")


def build_kdtree():
    global _KDTREE, _NODE_IDS_ARRAY
    if not NODE_COORDS:
        log.warning("Cannot build KD-Tree: NODE_COORDS is empty")
        return
    ids = list(NODE_COORDS.keys())
    coords = np.array([NODE_COORDS[nid] for nid in ids], dtype=np.float64)
    _KDTREE = cKDTree(coords)
    _NODE_IDS_ARRAY = np.array(ids, dtype=np.int64)
    log.info(f"KD-Tree built for {len(ids):,} nodes")


# ── Global State ────────────────────────────────────────────────────
G: Optional[nx.MultiGraph] = None
NODE_COORDS: Dict[int, tuple] = {}   # node_id -> (lon, lat)
FACILITIES: List[Dict] = []
EDGES_BY_NODE: Dict[int, List[Dict]] = {}  # node_id -> [{v, walk_time_s, length_m, fclass}]
GRAPH_NODE_SET: set = set()  # 仅图内节点，用于 snap 搜索加速
_KDTREE: Optional[cKDTree] = None
_NODE_IDS_ARRAY: Optional[np.ndarray] = None  # node_ids aligned with KD-Tree


# ── Request / Response Models ───────────────────────────────────────
class SnapRequest(BaseModel):
    lon: float
    lat: float
    threshold_deg: float = 0.005


class SnapResponse(BaseModel):
    node_id: int
    lon: float
    lat: float
    snapped: bool


class RouteRequest(BaseModel):
    from_lon: float
    from_lat: float
    to_lon: float
    to_lat: float


class RouteStep(BaseModel):
    fclass: str
    instruction: str
    length_m: float
    time_s: float
    distance_m: float = Field(default=0.0, description="Alias for JS compatibility")
    duration_s: float = Field(default=0.0, description="Alias for JS compatibility")


class RouteResponse(BaseModel):
    success: bool
    total_time_s: float
    total_distance_m: float
    geometry: List[List[float]]  # [[lon, lat], ...]
    steps: List[RouteStep]
    distance_m: float = Field(default=0.0, description="Alias for JS compatibility")
    duration_s: float = Field(default=0.0, description="Alias for JS compatibility")


class FacilityRequest(BaseModel):
    lon: float
    lat: float
    n_per_type: int = 3


class FacilityResult(BaseModel):
    facility_type: str
    name: str
    node_id: int
    walk_time_s: float
    distance_m: float
    lon: float
    lat: float


class ClosestFacilitiesResponse(BaseModel):
    origin_node_id: int
    origin_lon: float
    origin_lat: float
    facilities: List[FacilityResult]


class ServiceAreaRequest(BaseModel):
    lon: float
    lat: float
    time_min: float = 10.0
    time_max: Optional[float] = None


class ServiceAreaResponse(BaseModel):
    time_threshold_min: float
    reachable_nodes: int
    reachable_area_km2: float
    polygon: List[List[float]]
    reachable_edges: List[Dict]
    node_coords: Dict[int, List[float]]


class LivingCircleResponse(BaseModel):
    """15分钟生活圈分析结果"""
    origin_node_id: int
    origin_lon: float
    origin_lat: float
    time_min: float
    radius_m: float
    area_km2: float
    reachable_node_count: int
    reachable_nodes: int = Field(default=0, description="Alias for compatibility")
    transit_count: int
    facility_counts: Dict[str, int] = Field(default_factory=dict, description="设施数量统计（按类型）")
    facilities_within: Dict[str, int] = Field(default_factory=dict, description="Alias for facility_counts")
    # POI details within circle
    facilities: List[Dict]  # [{name, type, subtype, lon, lat, walk_time_s, distance_m}, ...]
    polygon: List[List[float]]  # [[lon, lat], ...] - convex hull of reachable area


class CoverageGridCell(BaseModel):
    """Coverage grid cell with properties"""
    cell_id: str
    center_lon: float
    center_lat: float
    coverage_score: float  # 0-100, weighted score of facilities
    facilities_count: int
    transit_count: int
    reachable_nodes: int
    time_to_nearest_transit_min: Optional[float] = None


class CoverageGridResponse(BaseModel):
    """Coverage grid analysis result"""
    n: int  # grid size (n x n)
    time_min: float
    bounds: Dict[str, float]
    total_cells: int
    cells: List[Dict]  # GeoJSON-compatible with properties
    geojson: Dict  # Full GeoJSON FeatureCollection


# ── Core Algorithm: Dijkstra ──────────────────────────────────────
def dijkstra(G, source, cost_attr="walk_time_s"):
    """
    Fast Dijkstra using heapq.
    Returns (distances: dict, predecessors: dict).
    """
    dist = {source: 0.0}
    prev = {source: None}
    pq = [(0.0, source)]
    visited = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in visited:
            continue
        visited.add(u)
        for v in G.neighbors(u):
            if v in visited:
                continue
            edge_data = G.get_edge_data(u, v)
            if not edge_data:
                continue
            edge = edge_data[0]  # MultiGraph can have parallel edges
            cost = edge.get(cost_attr, edge.get("length_m", 1.0))
            alt = d + cost
            if v not in dist or alt < dist[v]:
                dist[v] = alt
                prev[v] = u
                heapq.heappush(pq, (alt, v))

    return dist, prev


def reconstruct_geometry(G, source, target, prev) -> Optional[List[List[float]]]:
    """Reconstruct line coords from Dijkstra predecessors."""
    if target not in prev:
        return None
    path = []
    curr = target
    while curr is not None:
        path.append(curr)
        curr = prev.get(curr)
        if curr is None:
            break
    path.reverse()

    coords = []
    for nid in path:
        if nid in NODE_COORDS:
            coords.append([NODE_COORDS[nid][0], NODE_COORDS[nid][1]])
    return coords if len(coords) >= 2 else None


FCLASS_TO_CN = {
    "footway":       "步行道",
    "service":       "服务性道路",
    "residential":   "居住区道路",
    "primary":       "主干道",
    "secondary":     "次干道",
    "tertiary":      "支路",
    "unclassified":  "普通道路",
    "living_street": "生活街道",
    "pedestrian":    "步行街",
    "track":         "园路",
    "path":          "小径",
    "steps":         "台阶/阶梯",
    "primary_link":  "主路匝道",
    "secondary_link":"次路匝道",
    "tertiary_link": "支路匝道",
    "trunk":         "快速路",
    "trunk_link":    "快速路匝道",
    "motorway":      "高速公路",
    "motorway_link": "高速入口",
    "cycleway":      "骑行道",
    "bridleway":     "马道",
    "corridor":      "室内通道",
    "unknown":       "未知道路",
}

def compute_route_steps(G, source, target, prev) -> List[Dict]:
    """Break down route by fclass segments."""
    if target not in prev:
        return []
    path = []
    curr = target
    while curr is not None:
        path.append(curr)
        curr = prev.get(curr)
    path.reverse()

    steps = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        edge_data = G.get_edge_data(u, v)
        if not edge_data:
            continue
        edge = edge_data[0]
        fclass = edge.get("fclass", "unknown")
        steps.append({
            "fclass":       fclass,
            "instruction":  FCLASS_TO_CN.get(fclass, fclass),
            "length_m":      round(edge.get("length_m", 0), 1),
            "time_s":        round(edge.get("walk_time_s", 0), 1),
        })
    return steps


# ── Coverage Grid Cache (for performance) ───────────────────────────
_COVERAGE_CACHE: Dict[tuple, Dict] = {}
_COVERAGE_CACHE_MAX = 5000


def snap_point(lon: float, lat: float, threshold_deg: float = 0.005) -> Optional[int]:
    """Snap lon/lat to nearest GRAPH node using KD-Tree. Returns node_id or None."""
    if _KDTREE is None or G is None:
        return None
    m_per_deg_lat = 111320
    m_per_deg_lon = 111320 * math.cos(math.radians(lat))
    threshold_m = threshold_deg * min(m_per_deg_lat, m_per_deg_lon)
    query_point = np.array([[lon, lat]], dtype=np.float64)
    # Query enough candidates then filter to nodes actually in G
    k = min(50, len(_NODE_IDS_ARRAY))
    distances, indices = _KDTREE.query(query_point, k=k, distance_upper_bound=threshold_m * 2)
    for i in range(k):
        raw_idx = int(indices.flat[i])
        if raw_idx >= len(_NODE_IDS_ARRAY):
            break
        node_id = int(_NODE_IDS_ARRAY[raw_idx])
        if node_id in G:
            return node_id
    return None


# ── Convex Hull (Graham Scan) ──────────────────────────────────────
def convex_hull(points: List[List[float]]) -> List[List[float]]:
    """
    Compute convex hull using Graham scan algorithm.
    Input: [[lon, lat], ...]
    Output: [[lon, lat], ...] - polygon points in CCW order
    """
    if len(points) < 3:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    # Sort by x (lon), then y (lat) - use key to avoid shadowing
    sorted_pts = sorted(points, key=lambda p: (p[0], p[1]))
    if len(sorted_pts) <= 1:
        return sorted_pts[:]

    # Build lower hull
    lower = []
    for p in sorted_pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    # Build upper hull
    upper = []
    for p in reversed(sorted_pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    # Concatenate - remove last point of each half because it's repeated
    return lower[:-1] + upper[:-1]


def compute_convex_hull_area(polygon: List[List[float]]) -> float:
    """
    Compute area of polygon using shoelace formula.
    Input: [[lon, lat], ...] in degrees
    Output: area in km²
    """
    if len(polygon) < 3:
        return 0.0

    # Convert to approximate meters using center point
    center_lon = sum(p[0] for p in polygon) / len(polygon)
    center_lat = sum(p[1] for p in polygon) / len(polygon)

    # Approximate conversion factors at this latitude
    lat_to_m = 111320  # meters per degree latitude
    lon_to_m = 111320 * abs(math.cos(math.radians(center_lat)))

    # Convert to meters
    pts_m = [[p[0] * lon_to_m, p[1] * lat_to_m] for p in polygon]

    # Shoelace formula
    area = 0.0
    for i in range(len(pts_m)):
        j = (i + 1) % len(pts_m)
        area += pts_m[i][0] * pts_m[j][1]
        area -= pts_m[j][0] * pts_m[i][1]
    area = abs(area) / 2.0

    return area / 1_000_000  # m² to km²


# ── Startup ─────────────────────────────────────────────────────────
@app.on_event("startup")
async def load_network():
    global G, NODE_COORDS, FACILITIES, EDGES_BY_NODE, GRAPH_NODE_SET
    log.info("Loading network from disk...")
    try:
        if GRAPH_PATH.exists():
            with open(GRAPH_PATH, "rb") as f:
                G = pickle.load(f)
            # Keep only the largest connected component for routing
            import networkx as _nx
            all_components = [G.subgraph(c) for c in _nx.connected_components(G)]
            if all_components:
                all_components.sort(key=lambda s: s.number_of_nodes(), reverse=True)
                G = all_components[0]
                log.info(f"  Filtered to largest component: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (from {len(all_components)} total components)")
            GRAPH_NODE_SET = set(G.nodes())
            log.info(f"  Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        else:
            log.warning(f"  Graph file not found: {GRAPH_PATH}")

        if NODES_PATH.exists():
            with open(NODES_PATH, "r", encoding="utf-8") as f:
                nodes_data = json.load(f)
            for node in nodes_data:
                nid = node["node_id"]
                lon, lat = node["lon"], node["lat"]
                NODE_COORDS[nid] = (lon, lat)
                # 补全图节点坐标属性（导出时可能丢失）
                if G and nid in G:
                    G.nodes[nid]["lon"] = lon
                    G.nodes[nid]["lat"] = lat
            log.info(f"  Nodes: {len(NODE_COORDS)}")

        build_kdtree()

        if FACILITIES_PATH.exists():
            with open(FACILITIES_PATH, "r", encoding="utf-8") as f:
                FACILITIES = json.load(f)
            log.info(f"  Facilities: {len(FACILITIES)}")

        if EDGES_PATH.exists():
            with open(EDGES_PATH, "r", encoding="utf-8") as f:
                edges_list = json.load(f)
            for e in edges_list:
                u, v = e["u"], e["v"]
                edge_dict = {
                    "v": v,
                    "walk_time_s": e.get("walk_time_s", 0),
                    "length_m": e.get("length_m", 0),
                    "fclass": e.get("fclass", "unknown"),
                }
                EDGES_BY_NODE.setdefault(u, []).append(edge_dict)
            log.info(f"  Edge index built for {len(EDGES_BY_NODE)} nodes")

        log.info("Network loaded successfully.")
    except Exception as e:
        log.error(f"Failed to load network: {e}")
        raise


# ── Health ──────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "南山区步行可达性路由分析服务",
        "docs": "/docs",
        "api": "/api",
    }

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "network": "loaded" if G is not None else "not_loaded",
        "nodes": G.number_of_nodes() if G else 0,
        "edges": G.number_of_edges() if G else 0,
        "facilities": len(FACILITIES) if FACILITIES else 0,
    }


# ── Snap ────────────────────────────────────────────────────────────
@app.post("/api/snap", response_model=SnapResponse)
async def api_snap(req: SnapRequest):
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")
    node_id = snap_point(req.lon, req.lat, req.threshold_deg)
    if node_id is None:
        raise HTTPException(status_code=400, detail="Point not near walkable network")
    lon, lat = NODE_COORDS[node_id]
    return SnapResponse(node_id=node_id, lon=lon, lat=lat, snapped=True)


# ── Route (Async + Cache) ────────────────────────────────────
def _route_worker(src: int, dst: int) -> Optional[Dict]:
    """Thread-pool worker for Dijkstra. Returns (dist, prev) or None."""
    try:
        return dijkstra(G, src)
    except Exception:
        return None


def _compute_route_sync(src: int, dst: int) -> Optional[Dict]:
    """Synchronous route computation with in-process cache."""
    cache_key = (src, dst)
    if cache_key in _ROUTE_CACHE:
        return _ROUTE_CACHE[cache_key]

    result = _route_worker(src, dst)
    if result is None:
        return None

    dist, prev = result
    if dst not in dist:
        return None

    geometry = reconstruct_geometry(G, src, dst, prev)
    steps = compute_route_steps(G, src, dst, prev)
    total_time = dist[dst]
    total_dist = sum(s.get("length_m", 0) for s in steps)

    entry = {
        "total_time_s": round(total_time, 1),
        "total_distance_m": round(total_dist, 1),
        "geometry": geometry or [],
        "steps": [RouteStep(**s) for s in steps],
        "distance_m": round(total_dist, 1),
        "duration_s": round(total_time, 1),
    }

    # LRU eviction
    if len(_ROUTE_CACHE) >= _ROUTE_CACHE_MAX:
        # Remove oldest 20%
        keys_to_remove = list(_ROUTE_CACHE.keys())[: max(1, _ROUTE_CACHE_MAX // 5)]
        for k in keys_to_remove:
            del _ROUTE_CACHE[k]
    _ROUTE_CACHE[cache_key] = entry
    return entry


@app.post("/api/route", response_model=RouteResponse)
async def api_route(req: RouteRequest):
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")

    src = snap_point(req.from_lon, req.from_lat)
    dst = snap_point(req.to_lon, req.to_lat)
    if src is None or dst is None:
        raise HTTPException(status_code=400, detail="Start or end point not near network")

    # Run in thread pool so it doesn't block the event loop
    loop = asyncio.get_running_loop()
    result = await asyncio.wait_for(
        loop.run_in_executor(_executor, _compute_route_sync, src, dst),
        timeout=_ROUTE_TIMEOUT_S,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="No path found between points")

    return RouteResponse(success=True, **result)


# ── Closest Facilities ──────────────────────────────────────────────
@app.post("/api/closest-facilities", response_model=ClosestFacilitiesResponse)
async def api_closest_facilities(req: FacilityRequest):
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")

    src = snap_point(req.lon, req.lat)
    if src is None:
        raise HTTPException(status_code=400, detail="Origin point not near network")

    dist, _ = dijkstra(G, src)

    by_type: Dict[str, List[Dict]] = {}
    for f in FACILITIES:
        nid = f.get("node_id")
        if nid is None or nid not in dist:
            continue
        ft = normalize_ftype(f.get("facility_type", "other"))
        by_type.setdefault(ft, []).append({
            **f,
            "walk_time_s": round(dist[nid], 1),
            "distance_m": round(f.get("distance_m", 0), 1),
        })

    results = []
    for ft, facilities in by_type.items():
        facilities.sort(key=lambda x: x["walk_time_s"])
        for f in facilities[:req.n_per_type]:
            results.append(FacilityResult(
                facility_type=ft,
                name=f.get("name", "未知设施"),
                node_id=f.get("node_id"),
                walk_time_s=f["walk_time_s"],
                distance_m=f.get("distance_m", 0),
                lon=f.get("lon", 0),
                lat=f.get("lat", 0),
            ))

    src_lon, src_lat = NODE_COORDS.get(src, (req.lon, req.lat))
    return ClosestFacilitiesResponse(
        origin_node_id=src,
        origin_lon=src_lon,
        origin_lat=src_lat,
        facilities=results,
    )


# ── Service Area (Isochrone) ────────────────────────────────────────
@app.post("/api/service-area", response_model=ServiceAreaResponse)
async def api_service_area(req: ServiceAreaRequest):
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")

    src = snap_point(req.lon, req.lat)
    if src is None:
        raise HTTPException(status_code=400, detail="Origin point not near network")

    threshold_s = req.time_min * 60
    dist, prev = dijkstra(G, src, "walk_time_s")

    reachable_nodes = [nid for nid, d in dist.items() if d <= threshold_s]
    reachable_node_coords: Dict[int, List[float]] = {
        nid: list(NODE_COORDS[nid]) for nid in reachable_nodes if nid in NODE_COORDS
    }

    # Reachable edges: both endpoints reachable
    reachable_edges = []
    for nid in reachable_nodes:
        for v_data in EDGES_BY_NODE.get(nid, []):
            v = v_data["v"]
            if v in dist and dist.get(nid, float("inf")) <= threshold_s and dist[v] <= threshold_s:
                u_coords = NODE_COORDS.get(nid)
                v_coords = NODE_COORDS.get(v)
                if u_coords and v_coords:
                    reachable_edges.append({
                        "u": nid, "v": v,
                        "fclass": v_data.get("fclass", "unknown"),
                        "walk_time_s": v_data.get("walk_time_s", 0),
                    })

    # Compute convex hull polygon from reachable nodes
    reachable_coords = [
        NODE_COORDS[nid] for nid in reachable_nodes if nid in NODE_COORDS
    ]
    if len(reachable_coords) >= 3:
        hull_points = convex_hull(reachable_coords)
        polygon = hull_points + [hull_points[0]] if hull_points else []
        area_km2 = compute_convex_hull_area(polygon)
    elif len(reachable_coords) == 2:
        c0, c1 = reachable_coords[0], reachable_coords[1]
        polygon = [
            [c0[0], c0[1]],
            [c1[0], c0[1]],
            [c1[0], c1[1]],
            [c0[0], c1[1]],
            [c0[0], c0[1]],
        ]
        area_km2 = compute_convex_hull_area(polygon)
    else:
        polygon = []
        area_km2 = 0.0

    return ServiceAreaResponse(
        time_threshold_min=req.time_min,
        reachable_nodes=len(reachable_nodes),
        reachable_area_km2=round(area_km2, 4),
        polygon=polygon,
        reachable_edges=reachable_edges,
        node_coords=reachable_node_coords,
    )


# ── 15-Minute Living Circle (15分钟生活圈) ─────────────────────────────
@app.get("/api/living-circle", response_model=LivingCircleResponse)
async def api_living_circle(
    lat: float = Query(..., description="纬度"),
    lon: float = Query(..., description="经度"),
    time_threshold: float = Query(15.0, ge=5, le=60, description="可达时间阈值（分钟）"),
):
    """
    15分钟生活圈分析。
    基于步行路网计算从出发点的可达范围，并统计圈内各类设施数量。

    参数:
        lat: 纬度
        lon: 经度
        time_threshold: 可达时间阈值（分钟），默认15
    """
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")

    src = snap_point(lon, lat)
    if src is None:
        raise HTTPException(status_code=400, detail="Origin point not near network")

    threshold_s = time_threshold * 60
    dist, _ = dijkstra(G, src, "walk_time_s")

    # Collect reachable nodes
    reachable_nodes = [nid for nid, d in dist.items() if d <= threshold_s]
    reachable_node_set = set(reachable_nodes)

    # Calculate average radius from origin using Haversine (spherical)
    avg_radius = 0.0
    if reachable_nodes:
        total = 0.0
        for nid in reachable_nodes:
            if nid in NODE_COORDS:
                nl, nl2 = NODE_COORDS[nid]  # nl=lon, nl2=lat
                total += haversine_m(lat, lon, nl2, nl)
        avg_radius = total / len(reachable_nodes)

    # Compute convex hull polygon
    reachable_coords = [
        NODE_COORDS[nid] for nid in reachable_nodes if nid in NODE_COORDS
    ]
    if len(reachable_coords) >= 3:
        hull_points = convex_hull(reachable_coords)  # already [[lon,lat], ...]
        polygon = hull_points + [hull_points[0]] if hull_points else []
        area_km2 = compute_convex_hull_area(polygon)
    elif len(reachable_coords) == 2:
        polygon = [
            [reachable_coords[0][0], reachable_coords[0][1]],
            [reachable_coords[1][0], reachable_coords[0][1]],
            [reachable_coords[1][0], reachable_coords[1][1]],
            [reachable_coords[0][0], reachable_coords[1][1]],
            [reachable_coords[0][0], reachable_coords[0][1]],
        ]
        area_km2 = compute_convex_hull_area(polygon)
    else:
        polygon = []
        area_km2 = 0.0

    # Count and list facilities within reach
    facility_counts: Dict[str, int] = {}
    transit_count = 0
    facility_list: List[Dict] = []

    for f in FACILITIES:
        nid = f.get("node_id")
        if nid is None or nid not in dist:
            continue
        if dist[nid] > threshold_s:
            continue

        ft = normalize_ftype(f.get("facility_type", "other"))
        walk_time = dist[nid]
        distance_m = walk_time * 75  # approximate: 75m/min walking speed

        # Count by type
        facility_counts[ft] = facility_counts.get(ft, 0) + 1
        if ft == "transit":
            transit_count += 1

        # Determine transit subtype
        transit_subtype = None
        if ft == "transit":
            transit_subtype = classify_transit_subtype(
                f.get("name", ""),
                f.get("category1", ""),
                f.get("category2", ""),
            )

        facility_list.append({
            "name": f.get("name", "未知设施"),
            "type": ft,
            "subtype": transit_subtype,
            "lon": f.get("lon", 0),
            "lat": f.get("lat", 0),
            "walk_time_s": round(walk_time, 1),
            "walk_time_min": round(walk_time / 60, 2),
            "distance_m": round(distance_m, 0),
            "addr": f.get("addr", ""),
        })

    # Sort by walk time
    facility_list.sort(key=lambda x: x["walk_time_s"])

    src_lon, src_lat = NODE_COORDS.get(src, (lon, lat))

    return LivingCircleResponse(
        origin_node_id=src,
        origin_lon=src_lon,
        origin_lat=src_lat,
        time_min=time_threshold,
        radius_m=round(avg_radius, 0),
        area_km2=round(area_km2, 4),
        reachable_node_count=len(reachable_nodes),
        reachable_nodes=len(reachable_nodes),
        transit_count=transit_count,
        facility_counts=facility_counts,
        facilities_within=facility_counts,
        facilities=facility_list,
        polygon=polygon,
    )


# ── Living Circle Facilities ─────────────────────────────────────────
@app.get("/api/living-circle/facilities")
async def api_living_circle_facilities(
    lat: float = Query(..., description="纬度"),
    lon: float = Query(..., description="经度"),
    time_threshold: float = Query(15.0, ge=5, le=60, description="可达时间阈值（分钟）"),
    facility_types: Optional[str] = Query(None, description="逗号分隔的设施类型（如 transit,school,hospital）"),
):
    """
    查找步行可达范围内的所有设施，按步行时间排序。
    支持按类型过滤。

    参数:
        lat: 纬度
        lon: 经度
        time_threshold: 可达时间阈值（分钟），默认15
        facility_types: 逗号分隔的设施类型（如 transit,school,hospital）
    """
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")

    src = snap_point(lon, lat)
    if src is None:
        raise HTTPException(status_code=400, detail="Point not near walkable network")

    threshold_s = time_threshold * 60
    dist, _ = dijkstra(G, src, "walk_time_s")

    # Parse type filter
    type_filter = None
    if facility_types:
        type_filter = set(t.strip() for t in facility_types.split(",") if t.strip())

    # Collect facilities within reach
    facility_list: List[Dict] = []
    for f in FACILITIES:
        nid = f.get("node_id")
        if nid is None or nid not in dist:
            continue
        if dist[nid] > threshold_s:
            continue

        ft = normalize_ftype(f.get("facility_type", "other"))
        if type_filter and ft not in type_filter:
            continue

        walk_time = dist[nid]
        distance_m = walk_time * 75

        # Transit subtype
        transit_subtype = None
        if ft == "transit":
            transit_subtype = classify_transit_subtype(
                f.get("name", ""),
                f.get("category1", ""),
                f.get("category2", ""),
            )

        facility_list.append({
            "name": f.get("name", "未知设施"),
            "type": ft,
            "subtype": transit_subtype,
            "lon": f.get("lon", 0),
            "lat": f.get("lat", 0),
            "walk_time_s": round(walk_time, 1),
            "walk_time_min": round(walk_time / 60, 2),
            "distance_m": round(distance_m, 0),
            "addr": f.get("addr", ""),
        })

    # Sort by walk time
    facility_list.sort(key=lambda x: x["walk_time_s"])

    # Group by type
    by_type: Dict[str, List[Dict]] = {}
    for f in facility_list:
        ft = f["type"]
        by_type.setdefault(ft, []).append(f)

    return {
        "origin_lon": lon,
        "origin_lat": lat,
        "origin_node_id": src,
        "time_threshold": time_threshold,
        "total_facilities": len(facility_list),
        "facilities_by_type": {k: len(v) for k, v in by_type.items()},
        "facilities": facility_list,
    }


# ── Coverage Grid Analysis (网格化可达性分析) ─────────────────────────────
# 南山区边界范围
NANSHAN_BOUNDS = {
    "min_lon": 113.8210,
    "max_lon": 114.0938,
    "min_lat": 22.4670,
    "max_lat": 22.6736,
}


def _coverage_grid_cell(
    lon: float,
    lat: float,
    time_threshold: float,
    facility_type: Optional[str] = None,
) -> Dict:
    """
    Compute coverage metrics for a single grid cell.
    Uses caching to avoid redundant Dijkstra calculations.
    """
    # Check cache
    cache_key = (round(lon, 6), round(lat, 6), time_threshold, facility_type)
    if cache_key in _COVERAGE_CACHE:
        return _COVERAGE_CACHE[cache_key]

    if G is None:
        return {
            "center_lon": lon,
            "center_lat": lat,
            "coverage_score": 0,
            "facilities_count": 0,
            "transit_count": 0,
            "reachable_nodes": 0,
            "time_to_nearest_transit_min": None,
        }

    src = snap_point(lon, lat)
    if src is None:
        result = {
            "center_lon": lon,
            "center_lat": lat,
            "coverage_score": 0,
            "facilities_count": 0,
            "transit_count": 0,
            "reachable_nodes": 0,
            "time_to_nearest_transit_min": None,
        }
        _COVERAGE_CACHE[cache_key] = result
        return result

    threshold_s = time_threshold * 60
    dist, _ = dijkstra(G, src, "walk_time_s")

    # Count facilities
    facilities_count = 0
    transit_count = 0
    nearest_transit_time = None

    for f in FACILITIES:
        nid = f.get("node_id")
        if nid is None or nid not in dist:
            continue
        if dist[nid] > threshold_s:
            continue

        ft = normalize_ftype(f.get("facility_type", "other"))
        if facility_type and ft != facility_type:
            continue

        facilities_count += 1
        if ft == "transit":
            transit_count += 1
            walk_time = dist[nid]
            if nearest_transit_time is None or walk_time < nearest_transit_time:
                nearest_transit_time = walk_time

    reachable_nodes = len([n for n, d in dist.items() if d <= threshold_s])

    # Compute coverage score: weighted sum of facility counts
    # transit (地铁/公交) 高权重, school 次之, hospital 重要
    score = (
        transit_count * 3.0 +
        facilities_count * 1.0
    )
    # Normalize to 0-100
    coverage_score = min(100, round(score * 2, 1))

    result = {
        "center_lon": lon,
        "center_lat": lat,
        "coverage_score": coverage_score,
        "facilities_count": facilities_count,
        "transit_count": transit_count,
        "reachable_nodes": reachable_nodes,
        "time_to_nearest_transit_min": (
            round(nearest_transit_time / 60, 2)
            if nearest_transit_time is not None else None
        ),
    }

    # LRU cache eviction
    if len(_COVERAGE_CACHE) >= _COVERAGE_CACHE_MAX:
        keys_to_remove = list(_COVERAGE_CACHE.keys())[: max(1, _COVERAGE_CACHE_MAX // 5)]
        for k in keys_to_remove:
            del _COVERAGE_CACHE[k]

    _COVERAGE_CACHE[cache_key] = result
    return result


@app.get("/api/coverage-grid")
async def api_coverage_grid(
    bounds: Optional[str] = Query(None, description="边界范围，格式: min_lon,min_lat,max_lon,max_lat"),
    resolution: Optional[int] = Query(None, description="网格分辨率（米），与n参数二选一"),
    time_threshold: float = Query(15.0, ge=5, le=60, description="可达时间阈值（分钟）"),
    facility_type: Optional[str] = Query(None, description="设施类型过滤"),
    n: int = Query(10, ge=3, le=50, description="网格行列数（当resolution未指定时使用）"),
):
    """
    网格化可达性分析。
    将指定区域划分为网格，计算每个格点的可达设施覆盖情况。
    返回GeoJSON FeatureCollection，网格按coverage_score着色。

    参数:
        bounds: 边界范围，格式为"min_lon,min_lat,max_lon,max_lat"
        resolution: 网格分辨率（米），与n参数二选一。resolution优先级更高
        time_threshold: 可达时间阈值（分钟），默认15
        facility_type: 设施类型过滤
        n: 网格行列数（当resolution未指定时使用）
    """
    # Parse bounds
    if bounds:
        try:
            parts = bounds.split(",")
            if len(parts) == 4:
                min_lon = float(parts[0])
                min_lat = float(parts[1])
                max_lon = float(parts[2])
                max_lat = float(parts[3])
            else:
                raise HTTPException(status_code=400, detail="bounds格式错误，应为min_lon,min_lat,max_lon,max_lat")
        except ValueError:
            raise HTTPException(status_code=400, detail="bounds参数包含无效数字")
    else:
        bounds_dict = NANSHAN_BOUNDS
        min_lon = bounds_dict["min_lon"]
        max_lon = bounds_dict["max_lon"]
        min_lat = bounds_dict["min_lat"]
        max_lat = bounds_dict["max_lat"]

    # Calculate grid size from resolution (meters)
    if resolution:
        # Convert resolution in meters to approximate degree step
        m_per_deg_lat = 111320
        m_per_deg_lon = 111320 * abs(math.cos(math.radians((min_lat + max_lat) / 2)))
        lat_step_deg = resolution / m_per_deg_lat
        lon_step_deg = resolution / m_per_deg_lon

        # Calculate n from resolution
        n_lon = max(3, int(round((max_lon - min_lon) / lon_step_deg)))
        n_lat = max(3, int(round((max_lat - min_lat) / lat_step_deg)))
        n = min(n_lon, n_lat)  # Use smaller dimension
        n = min(n, 50)  # Cap at 50 for performance

        lon_step = (max_lon - min_lon) / n
        lat_step = (max_lat - min_lat) / n
    else:
        lon_step = (max_lon - min_lon) / n
        lat_step = (max_lat - min_lat) / n

    cells: List[Dict] = []
    features: List[Dict] = []

    cell_id = 0
    for i in range(n):
        for j in range(n):
            cell_lon = min_lon + (i + 0.5) * lon_step
            cell_lat = min_lat + (j + 0.5) * lat_step

            metrics = _coverage_grid_cell(cell_lon, cell_lat, time_threshold, facility_type)

            # Cell corners for polygon
            cell_min_lon = min_lon + i * lon_step
            cell_max_lon = min_lon + (i + 1) * lon_step
            cell_min_lat = min_lat + j * lat_step
            cell_max_lat = min_lat + (j + 1) * lat_step

            cell_id_str = f"cell_{i}_{j}"
            cell_data = {
                "cell_id": cell_id_str,
                "row": i,
                "col": j,
                **metrics,
            }
            cells.append(cell_data)

            # GeoJSON polygon feature
            feature = {
                "type": "Feature",
                "id": cell_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [cell_min_lon, cell_min_lat],
                        [cell_max_lon, cell_min_lat],
                        [cell_max_lon, cell_max_lat],
                        [cell_min_lon, cell_max_lat],
                        [cell_min_lon, cell_min_lat],
                    ]],
                },
                "properties": metrics,
            }
            features.append(feature)
            cell_id += 1

    # Build GeoJSON FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Stats summary
    scores = [c["coverage_score"] for c in cells]
    avg_score = sum(scores) / len(scores) if scores else 0
    max_score = max(scores) if scores else 0
    min_score = min(scores) if scores else 0

    return {
        "n": n,
        "time_threshold": time_threshold,
        "resolution_m": resolution,
        "facility_type": facility_type,
        "bounds": {
            "min_lon": min_lon,
            "max_lon": max_lon,
            "min_lat": min_lat,
            "max_lat": max_lat,
        },
        "total_cells": len(cells),
        "average_coverage_score": round(avg_score, 2),
        "max_coverage_score": max_score,
        "min_coverage_score": min_score,
        "cells": cells,
        "geojson": geojson,
    }


# ── Facilities List (Paginated + Search) ─────────────────────
@app.get("/api/facilities")
async def api_facilities(
    page: int = Query(1, ge=1, description="页码（从1开始）"),
    limit: int = Query(100, ge=1, le=500, description="每页数量"),
    type: str = Query(None, description="设施类型过滤（如 transit, school）"),
    q: str = Query(None, description="名称搜索关键词"),
    min_confidence: float = Query(None, ge=0, le=1, description="最低置信度"),
):
    """
    分页设施列表，支持类型过滤、名称搜索、置信度过滤。
    """
    filtered = []

    # Known subway/bus node_ids for distance-based confidence scoring
    subway_nodes = set()
    bus_nodes = set()
    for f in FACILITIES:
        ft = normalize_ftype(f.get("facility_type", "other"))
        if ft == "transit":
            sub = classify_transit_subtype(
                f.get("name", ""),
                f.get("category1", ""),
                f.get("category2", ""),
            )
            if sub == "subway":
                subway_nodes.add(f.get("node_id"))
            elif sub == "bus":
                bus_nodes.add(f.get("node_id"))

    for f in FACILITIES:
        ft = normalize_ftype(f.get("facility_type", "other"))

        # Type filter
        if type and ft != type and f.get("facility_type", "") != type:
            continue

        # Keyword search
        if q:
            name = f.get("name", "").lower()
            addr = f.get("addr", "").lower()
            if q.lower() not in name and q.lower() not in addr:
                continue

        # Confidence filter
        if min_confidence is not None:
            conf = calculate_poi_confidence(
                f.get("name", ""),
                ft,
                f.get("category1", ""),
                f.get("category2", ""),
            )
            if conf < min_confidence:
                continue

        # Assign transit subtype
        entry = {**f, "facility_type": ft}
        if ft == "transit":
            entry["transit_subtype"] = classify_transit_subtype(
                f.get("name", ""),
                f.get("category1", ""),
                f.get("category2", ""),
            )
            entry["confidence"] = calculate_poi_confidence(
                f.get("name", ""), ft,
                f.get("category1", ""), f.get("category2", ""),
            )

        filtered.append(entry)

    total = len(filtered)
    start = (page - 1) * limit
    end = start + limit
    page_items = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "facilities": page_items,
    }


# ── Transit Stations ──────────────────────────────────────────────
@app.get("/api/transit/stations")
async def api_transit_stations(
    subtype: str = Query(None, description="子类型: subway, bus, railway, ferry, taxi, parking"),
    min_confidence: float = Query(0.5, ge=0, le=1, description="最低置信度"),
):
    """
    交通站点列表，按 transit_subtype 细分。
    用于前端显示地铁站、公交站等专用图标。
    """
    results = []
    for f in FACILITIES:
        ft = normalize_ftype(f.get("facility_type", "other"))
        if ft != "transit":
            continue

        ts = classify_transit_subtype(
            f.get("name", ""),
            f.get("category1", ""),
            f.get("category2", ""),
        )
        if subtype and ts != subtype:
            continue

        conf = calculate_poi_confidence(
            f.get("name", ""), ft,
            f.get("category1", ""), f.get("category2", ""),
        )
        if conf < min_confidence:
            continue

        results.append({
            "node_id": f.get("node_id"),
            "name": f.get("name", "未知站点"),
            "transit_subtype": ts,
            "confidence": round(conf, 3),
            "lon": f.get("lon", 0),
            "lat": f.get("lat", 0),
            "addr": f.get("addr", ""),
        })

    return {
        "count": len(results),
        "subtype": subtype or "all",
        "stations": results,
    }


@app.get("/api/transit/nearby")
async def api_transit_nearby(
    lat: float = Query(..., description="纬度"),
    lon: float = Query(..., description="经度"),
    radius: float = Query(500, ge=50, le=5000, description="搜索半径（米）"),
    subtype: str = Query(None, description="子类型过滤"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    查找指定坐标附近的交通站点。
    """
    matches = []
    for f in FACILITIES:
        f_lat = f.get("lat", 0)
        f_lon = f.get("lon", 0)
        dist = haversine_m(lat, lon, f_lat, f_lon)
        if dist > radius:
            continue

        ft = normalize_ftype(f.get("facility_type", "other"))
        if ft != "transit":
            continue

        ts = classify_transit_subtype(
            f.get("name", ""),
            f.get("category1", ""),
            f.get("category2", ""),
        )
        if subtype and ts != subtype:
            continue

        conf = calculate_poi_confidence(
            f.get("name", ""), ft,
            f.get("category1", ""), f.get("category2", ""),
        )

        matches.append({
            "name": f.get("name", "未知站点"),
            "transit_subtype": ts,
            "confidence": round(conf, 3),
            "lon": f_lon,
            "lat": f_lat,
            "distance_m": round(dist, 0),
            "addr": f.get("addr", ""),
        })

    matches.sort(key=lambda x: x["distance_m"])
    return {"count": len(matches), "nearby": matches[:limit]}


# ── Stats ───────────────────────────────────────────────────────────
@app.get("/api/stats")
async def api_stats():
    if G is None:
        raise HTTPException(status_code=503, detail="Network not loaded")
    by_fclass: Dict[str, int] = {}
    for _, _, data in G.edges(data=True):
        f = data.get("fclass", "unknown")
        by_fclass[f] = by_fclass.get(f, 0) + 1
    by_ft: Dict[str, int] = {}
    transit_sub: Dict[str, int] = {}
    for f in FACILITIES:
        ft = normalize_ftype(f.get("facility_type", "other"))
        by_ft[ft] = by_ft.get(ft, 0) + 1
        if ft == "transit":
            ts = classify_transit_subtype(
                f.get("name", ""),
                f.get("category1", ""),
                f.get("category2", ""),
            )
            transit_sub[ts] = transit_sub.get(ts, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "walkable_edges": sum(1 for _, _, d in G.edges(data=True) if d.get("walkable", True)),
        "edges_by_fclass": dict(sorted(by_fclass.items(), key=lambda x: -x[1])),
        "facilities_by_type": dict(sorted(by_ft.items(), key=lambda x: -x[1])),
        "transit_by_subtype": dict(sorted(transit_sub.items(), key=lambda x: -x[1])),
        "route_cache_size": len(_ROUTE_CACHE),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
