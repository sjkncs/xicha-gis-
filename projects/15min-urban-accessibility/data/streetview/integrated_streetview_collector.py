# -*- coding: utf-8 -*-
"""
================================================================================
深圳南山区街景影像与POI数据采集系统
Integrated Street View & POI Acquisition System for Nanshan District, Shenzhen
================================================================================

【研究背景】
本研究旨在通过街景影像和POI数据，验证15分钟城市可达性假说：
是否存在系统性因素（如城中村vs高端社区）导致可达性测量结果出现偏差？
本系统为实地数据采集提供自动化的采样、分类、采集流程。

【数据来源】
  - 路网: OSM OpenStreetMap (nanshan_road_network.shp)
  - 楼栋: 南山区房屋楼栋基础数据 CSV
  - 街景: 百度全景 / 高德地图 / 腾讯地图 API
  - POI:  高德地图 Web服务 API
  - AOI:  高德地图 AOI边界查询 (高阶权限)

【功能模块】
  1. 坐标转换: WGS84 <-> GCJ-02 <-> BD-09
  2. 路网采样: 沿OSM道路等间隔插值采样
  3. 形态分类: 基于楼栋名称+密度对采样点进行城市形态分类
  4. 分层降采样: 确保城中村/高端社区在有限样本中有足够代表性
  5. POI密度分析: 高德周边搜索 + 多半径密度计算
  6. AOI边界查询: 城中村/小区精确边界获取
  7. 地理编码: 地址<->坐标互转
  8. 行政区划: 南山区边界自动获取
  9. 天气数据: 采集时的气象数据（环境因素）
  10. 路径规划: 15分钟步行可达范围计算
  11. 街景采集: 百度全景/高德/腾讯街景影像多方向采集
  12. 批量请求管理: 多Key轮询+配额控制+断点续传
|  13. 静态地图采集: 高德静态地图（标注/路径/标签叠加，500次/日）
【高德API Key申请】
  官网: https://lbs.amap.com/
  控制台: https://console.amap.com/dev/key/app
  街景权限: 需单独申请 (工单/商务)
  AOI边界权限: 需工单申请高阶权限

  具体说明见文件底部: === 高德API配置详解 ===

依赖:
  pip install geopandas pandas requests Pillow tqdm shapely scipy numpy

================================================================================
"""

import os
import sys
import math
import time
import json
import hashlib
import argparse
import warnings
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, Union
from datetime import datetime, date
from functools import lru_cache

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


# ============================================================================
# 路径配置
# ============================================================================

BASE_DIR = Path(r'E:\xicha gis 智能定位')
PROJECT_DIR = BASE_DIR / 'projects' / '15min-urban-accessibility'
OSM_DIR = PROJECT_DIR / 'osm_data'
BUILDING_CSV = PROJECT_DIR / 'building_data' / '南山区-房屋楼栋基础数据_2920004003598.csv'

OUTPUT_DIR = PROJECT_DIR / 'data' / 'streetview' / 'integrated_collection'
SAMPLES_DIR = OUTPUT_DIR / 'samples'
IMAGES_DIR = OUTPUT_DIR / 'images'
META_DIR = OUTPUT_DIR / 'metadata'


# ============================================================================
# 采样与分类配置
# ============================================================================

# 南山区大致边界 (WGS84) — 精确边界由 DistrictAPI 自动获取
# 深圳市南山区 adcode: 440305
NANSHAN_ADCODE = '440305'

# 沿路网采样间隔 (米) — 按道路类型分级
ROAD_SAMPLE_INTERVALS: Dict[str, int] = {
    # OSM fclass → 采样间隔(米)
    # 等级越高（主干道）的道路越重要，采样间隔越小
    'motorway':      100,
    'trunk':         100,
    'primary':        80,
    'secondary':     120,
    'tertiary':      150,
    'residential':   200,
    'service':       250,
    'unclassified':  250,
    'footway':       150,
    'pedestrian':    150,
    'steps':         100,
    'path':          200,
    'track':         300,
    'cycleway':      200,
    'living_street': 200,
    'primary_link':  100,
    'secondary_link':120,
    'tertiary_link': 150,
    'trunk_link':    100,
    'motorway_link': 100,
}

# 用途类型 → 中文名称
USAGE_TYPE_MAP: Dict[int, str] = {
    1: '住宅', 2: '住宅', 3: '商住混合',
    4: '商业', 5: '工业', 6: '基础设施',
    7: '其他', 8: '公共', 0: '未知',
}


# ============================================================================
# 坐标转换 (WGS84 <-> GCJ-02 <-> BD-09)
# ============================================================================
# 说明:
#   WGS84:  GPS标准坐标 (国际通用)
#   GCJ-02: 中国国测局加密坐标 (高德、腾讯、谷歌中国使用)
#   BD-09:  百度私有加密坐标 (百度地图使用)
#
# 转换关系:
#   WGS84 --wgs84_to_gcj02/gcj02_to_wgs84--> GCJ-02
#   GCJ-02 --gcj02_to_bd09/bd09_to_gcj02--> BD-09
#   WGS84 --wgs84_to_bd09/bd09_to_wgs84--> BD-09

PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323


def _transform_lat(x: float, y: float) -> float:
    """
    国测局坐标转换辅助函数 — 纬度变换量
    内部使用，无需单独调用
    """
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320.0 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    """
    国测局坐标转换辅助函数 — 经度变换量
    内部使用，无需单独调用
    """
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """
    WGS84 → GCJ-02 (高德/腾讯/谷歌中国坐标)

    Args:
        lng: WGS84 经度
        lat: WGS84 纬度

    Returns:
        (gcj_lng, gcj_lat)
    """
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat


def gcj02_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ-02 → BD-09 (百度坐标)

    Args:
        lng: GCJ-02 经度
        lat: GCJ-02 纬度

    Returns:
        (bd_lng, bd_lat)
    """
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    """WGS84 → BD-09 (百度坐标)，等价于 wgs84→gcj02→bd09"""
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


def bd09_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """BD-09 → GCJ-02"""
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x * x + y * y) + 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """
    GCJ-02 → WGS84 (逆向转换)

    Args:
        lng: GCJ-02 经度
        lat: GCJ-02 纬度

    Returns:
        (wgs_lng, wgs_lat)
    """
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng - dlng, lat - dlat


def bd09_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
    """BD-09 → WGS84，等价于 bd09→gcj02→wgs84"""
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


def haversine_m(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Haversine公式计算两点间球面距离（米）"""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ============================================================================
# 数据加载
# ============================================================================

def load_road_network(shp_path: Path) -> 'gpd.GeoDataFrame':
    """
    加载OSM路网shapefile，自动投影至WGS84。

    Args:
        shp_path: shapefile文件路径

    Returns:
        投影到EPSG:4326的GeoDataFrame
    """
    import geopandas as gpd
    print(f"[路网] 加载Shapefile: {shp_path}")
    gdf = gpd.read_file(str(shp_path))
    if gdf.crs and str(gdf.crs).upper() not in ('EPSG:4326', '4326'):
        gdf = gdf.to_crs('EPSG:4326')
    print(f"[路网] 共 {len(gdf)} 条道路, 类型: {list(gdf.geom_type.unique())}")
    return gdf


def load_building_data() -> pd.DataFrame:
    """
    加载楼栋数据并做数据清洗。

    注意: 原始CSV的列名与实际数据存在反向——
    '中心坐标'列的值实际是经度(113.9X)，'中心点坐标'列的值是纬度(22.5X)
    """
    print(f"[建筑] 加载: {BUILDING_CSV}")
    df = pd.read_csv(BUILDING_CSV, dtype=str, keep_default_na=False)
    df['lng'] = pd.to_numeric(df['中心坐标'], errors='coerce')
    df['lat'] = pd.to_numeric(df['中心点坐标'], errors='coerce')
    df['floor_count'] = pd.to_numeric(df['总层数'], errors='coerce').fillna(0).astype(int)
    df['usage_type'] = pd.to_numeric(df['使用用途'], errors='coerce').fillna(0).astype(int)
    df['building_name'] = df['名称'].str.strip()
    df = df.dropna(subset=['lng', 'lat'])

    # 南山区范围过滤（宽泛范围，防止遗漏边界楼栋）
    df = df[
        (df['lng'] >= 113.85) & (df['lng'] <= 114.45) &
        (df['lat'] >= 22.40) & (df['lat'] <= 22.80)
    ]
    print(f"[建筑] 有效楼栋: {len(df)} 个")
    return df


# ============================================================================
# 沿路网采样
# ============================================================================

def sample_along_roads(
    road_gdf: 'gpd.GeoDataFrame',
    sample_intervals: Dict[str, int],
    n_max: Optional[int] = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    沿OSM路网进行等间隔插值采样。

    对每条道路Edge:
      1. 根据道路类型(fclass)确定采样间隔
      2. 沿LineString坐标序列等间隔取点
      3. 每个采样点附带: lng, lat, road_fclass, road_name, edge_id

    Args:
        road_gdf: OSM路网GeoDataFrame
        sample_intervals: 道路类型→采样间隔(米)的映射
        n_max: 最大采样点数（None=无限制）
        seed: 随机种子

    Returns:
        采样点DataFrame
    """
    from shapely import LineString
    rng = np.random.default_rng(seed)
    del rng  # 当前为确定性采样（间隔固定），如需随机采样可放开

    print(f"[采样] 沿 {len(road_gdf)} 条道路采样...")
    all_points = []

    for idx, row in road_gdf.iterrows():
        fclass = row.get('fclass', 'unclassified')
        road_name = row.get('name', '')
        edge_id = str(row.get('osm_id', idx))
        interval = sample_intervals.get(fclass, 200)

        geom = row.geometry
        if geom is None:
            continue

        # 获取线的坐标序列（处理MultiLineString和LineString）
        if geom.geom_type == 'MultiLineString':
            coords_seq = []
            for part in geom.geoms:
                coords_seq.extend(list(part.coords)[:-1])
            coords_seq.append(geom.geoms[-1].coords[-1])
        else:
            coords_seq = list(geom.coords)

        if len(coords_seq) < 2:
            continue

        # 计算沿线累积距离
        cumdist = [0.0]
        for i in range(1, len(coords_seq)):
            d = haversine_m(
                coords_seq[i - 1][0], coords_seq[i - 1][1],
                coords_seq[i][0], coords_seq[i][1]
            )
            cumdist.append(cumdist[-1] + d)

        total_length = cumdist[-1]
        if total_length < 5:
            continue

        # 等间隔采样
        n_intervals = max(1, int(total_length / interval))
        for k in range(n_intervals + 1):
            target_dist = k * interval
            if target_dist > total_length:
                break

            pos = _binary_search_cumdist(cumdist, target_dist)
            t = pos['t']
            i0 = pos['i0']
            i1 = pos['i1']
            i0 = min(i0, len(coords_seq) - 2)
            i1 = min(i1, len(coords_seq) - 1)

            lng = coords_seq[i0][0] + t * (coords_seq[i1][0] - coords_seq[i0][0])
            lat = coords_seq[i0][1] + t * (coords_seq[i1][1] - coords_seq[i0][1])

            all_points.append({
                'lng': lng, 'lat': lat,
                'road_fclass': fclass,
                'road_name': str(road_name) if pd.notna(road_name) else '',
                'edge_id': edge_id,
                'dist_from_start': target_dist,
                'edge_total_m': total_length,
            })

    df = pd.DataFrame(all_points)
    df = df.drop_duplicates(subset=['lng', 'lat'])

    # 南山区大致边界过滤
    df = df[
        (df['lng'] >= 113.85) & (df['lng'] <= 114.45) &
        (df['lat'] >= 22.40) & (df['lat'] <= 22.80)
    ].copy()

    print(f"[采样] 原始采样点: {len(df)} 个")
    print("[采样] 道路类型分布:")
    for rt, cnt in df['road_fclass'].value_counts().head(8).items():
        print(f"  {rt}: {cnt} ({100 * cnt / len(df):.1f}%)")

    return df


def _binary_search_cumdist(cumdist: List[float], target: float) -> Dict[str, Any]:
    """
    二分查找累积距离数组中target对应的分段索引和线性插值比例。

    Args:
        cumdist: 累积距离列表 [0, d1, d2, ..., dn]
        target: 目标距离

    Returns:
        {'i0': 分段起点索引, 'i1': 分段终点索引, 't': 插值比例 [0,1]}
    """
    n = len(cumdist)
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if cumdist[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    i0 = max(0, lo - 1)
    i1 = lo
    if i0 == i1 or i1 >= len(cumdist):
        return {'i0': i0, 'i1': min(i0 + 1, len(cumdist) - 1), 't': 0.0}
    t = (target - cumdist[i0]) / (cumdist[i1] - cumdist[i0])
    return {'i0': i0, 'i1': i1, 't': max(0.0, min(1.0, t))}


# ============================================================================
# 城市形态分层
# ============================================================================

def classify_urban_form(
    sample_df: pd.DataFrame,
    building_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    对采样点进行城市形态分类（核心分层逻辑）。

    分类依据:
      1. 周边楼栋密度 (100m缓冲内楼栋数 + 平均层数)
      2. 城中村关键词匹配 (楼栋名含"村/新村/旧村/村民"，且楼层<=9)
      3. 高端社区关键词匹配 (楼栋名含"花园/山庄/广场/公馆...")

    形态类别:
      Village        — 城中村核心区 (城中村楼栋聚集，楼层低)
      Village Fringe — 城中村边缘区 (有零星城中村楼栋)
      High-End       — 高端社区 (多个高端小区楼栋附近)
      High-Rise      — 高层住宅区 (平均楼层>=20)
      Mid-Rise       — 中层住宅区 (8<=平均楼层<20)
      Low-Rise       — 低层住宅区 (1<平均楼层<8)
      Open/Other     — 开敞空间/其他 (无楼栋或密度极低)

    Args:
        sample_df: 采样点DataFrame
        building_df: 楼栋DataFrame

    Returns:
        追加了城市形态分类列的DataFrame
    """
    from scipy.spatial import cKDTree

    print("[形态] 城市形态分类...")
    df = sample_df.copy()

    # ── 1. 构建楼栋空间索引 ──
    bld_coords = building_df[['lng', 'lat']].values
    bld_tree = cKDTree(bld_coords)
    sample_coords = df[['lng', 'lat']].values

    densities_100m = []     # 100m缓冲内楼栋数量
    avg_floors_100m = [] # 100m缓冲内平均楼层
    nearest_dist = []      # 到最近楼栋的距离(度)

    R100 = 0.0009  # ≈ 100m in degree

    for lng, lat in sample_coords:
        ids = bld_tree.query_ball_point([lng, lat], r=R100)
        densities_100m.append(len(ids))
        if ids:
            floors = [building_df.iloc[i]['floor_count'] for i in ids]
            avg_floors_100m.append(np.mean(floors))
            dists, _ = bld_tree.query([lng, lat], k=1)
            nearest_dist.append(dists)
        else:
            avg_floors_100m.append(0.0)
            nearest_dist.append(float('inf'))

    df['bld_density_100m'] = densities_100m
    df['avg_floors_100m'] = avg_floors_100m
    df['nearest_bld_dist'] = nearest_dist

    # ── 2. 城中村识别 ──
    village_kws = ['村', '新村', '旧村', '村民']
    village_regex = '|'.join(village_kws)
    village_bld = building_df[
        building_df['building_name'].str.contains(village_regex, na=False, regex=True) &
        (building_df['floor_count'] <= 9)
    ]
    if len(village_bld) > 0:
        village_tree = cKDTree(village_bld[['lng', 'lat']].values)
        village_nearby = []
        for lng, lat in sample_coords:
            cnt = len(village_tree.query_ball_point([lng, lat], r=0.00045))  # ~50m
            village_nearby.append(cnt)
        df['village_nearby_cnt'] = village_nearby
    else:
        df['village_nearby_cnt'] = 0

    # ── 3. 高端社区识别 ──
    highend_kws = ['花园', '山庄', '广场', '公馆', '名苑', '御苑',
                   '海滨', '天利', '阳光', '观海', '豪庭', '雅居']
    highend_regex = '|'.join(highend_kws)
    highend_bld = building_df[
        building_df['building_name'].str.contains(highend_regex, na=False, regex=True)
    ]
    if len(highend_bld) > 0:
        highend_tree = cKDTree(highend_bld[['lng', 'lat']].values)
        highend_nearby = []
        for lng, lat in sample_coords:
            cnt = len(highend_tree.query_ball_point([lng, lat], r=0.00045))
            highend_nearby.append(cnt)
        df['highend_nearby_cnt'] = highend_nearby
    else:
        df['highend_nearby_cnt'] = 0

    # ── 4. 综合分类规则 ──
    def classify(row) -> str:
        if row['village_nearby_cnt'] >= 3 and row['avg_floors_100m'] <= 8:
            return 'Village'
        elif row['village_nearby_cnt'] >= 1:
            return 'Village Fringe'
        elif row['highend_nearby_cnt'] >= 2:
            return 'High-End'
        elif row['avg_floors_100m'] >= 20:
            return 'High-Rise'
        elif row['avg_floors_100m'] >= 8:
            return 'Mid-Rise'
        elif row['avg_floors_100m'] >= 1:
            return 'Low-Rise'
        else:
            return 'Open/Other'

    df['urban_form'] = df.apply(classify, axis=1)

    print("[形态] 分布:")
    for form, cnt in df['urban_form'].value_counts().items():
        print(f"  {form}: {cnt} ({100 * cnt / len(df):.1f}%)")

    return df


def stratified_downsample(
    sample_df: pd.DataFrame,
    n_target: int,
    building_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """
    分层降采样 — 确保城中村/高端社区在有限样本中有足够代表性。

    配额策略:
      60% 按城市形态权重分配 (优先保留 Village > Village Fringe > High-End)
      40% 按道路类型权重分配 (优先保留主干道采样点)

    优先级得分 = 形态权重 × 道路权重 × 聚集度奖励 × 密度奖励

    Args:
        sample_df: 形态分类后的采样点
        n_target: 目标采样数
        building_df: 楼栋数据（预留，用于额外特征）
        seed: 随机种子

    Returns:
        降采样后的DataFrame
    """
    df = sample_df.copy()
    n_total = len(df)

    if n_total <= n_target:
        return df

    print(f"[重采样] 从 {n_total} 个点分层降采样至 {n_target} 个...")

    # 形态优先级权重（值越大越优先保留）
    form_priority: Dict[str, float] = {
        'Village':         5.0,
        'Village Fringe':  3.0,
        'High-End':       4.0,
        'High-Rise':      1.5,
        'Mid-Rise':       1.2,
        'Low-Rise':       1.0,
        'Open/Other':     0.5,
    }

    # 道路类型优先级权重
    road_priority: Dict[str, float] = {
        'primary':    2.0, 'secondary': 2.0, 'tertiary': 1.5,
        'residential': 1.5, 'service': 1.2,
        'motorway':   1.5, 'trunk': 1.5,
        'unclassified': 1.0, 'footway': 1.0, 'pedestrian': 1.0,
        'steps': 1.0, 'cycleway': 0.8,
    }

    # 综合优先级得分
    def score(row) -> float:
        form_score = form_priority.get(row['urban_form'], 1.0)
        road_score = road_priority.get(row['road_fclass'], 0.5)
        village_bonus = 1.0 + row.get('village_nearby_cnt', 0) * 0.5
        highend_bonus = 1.0 + row.get('highend_nearby_cnt', 0) * 0.3
        density_bonus = 1.0 + row.get('bld_density_100m', 0) / 50.0
        return form_score * road_score * village_bonus * highend_bonus * density_bonus

    df['_priority'] = df.apply(score, axis=1)

    # ── 计算分层配额 ──
    form_counts = df['urban_form'].value_counts()
    total_weight = sum(form_priority.get(f, 1.0) for f in form_counts.index)
    base_quota = int(n_target * 0.6)   # 60% 按形态分配
    road_quota = n_target - base_quota  # 40% 按道路补充

    quotas = {}
    for form, cnt in form_counts.items():
        w = form_priority.get(form, 1.0)
        quotas[form] = max(1, int(base_quota * w / total_weight))

    # ── 按优先级选取 ──
    sampled_groups = []
    remaining = n_target

    for form in sorted(quotas.keys(), key=lambda f: -form_priority.get(f, 0)):
        subset = df[df['urban_form'] == form].copy()
        if len(subset) == 0:
            continue
        quota = min(quotas[form], len(subset))
        # 按优先级降序 + 均匀步长选取（保证空间分布均匀）
        subset = subset.sort_values('_priority', ascending=False)
        step = max(1, len(subset) // quota)
        selected = subset.iloc[::step].head(quota)
        sampled_groups.append(selected)
        remaining -= len(selected)

    # ── 剩余配额按全局优先级补充 ──
    if remaining > 0:
        picked_idx = pd.concat(sampled_groups).index
        remaining_df = df[~df.index.isin(picked_idx)].copy()
        remaining_df = remaining_df.sort_values('_priority', ascending=False)
        step = max(1, len(remaining_df) // remaining)
        sampled_groups.append(remaining_df.iloc[::step].head(remaining))

    result = pd.concat(sampled_groups, ignore_index=True)
    result = result.drop_duplicates(subset=['lng', 'lat']).reset_index(drop=True)
    result = result.drop(columns=['_priority'], errors='ignore')

    print(f"[重采样] 降采样后: {len(result)} 个")
    print("[重采样] 形态分布:")
    for form, cnt in result['urban_form'].value_counts().items():
        print(f"  {form}: {cnt} ({100 * cnt / len(result):.1f}%)")

    return result


# ============================================================================
# 高德API — 基础请求封装与批量管理
# ============================================================================
# 高德地图Web服务API基础URL:
#   Web服务(POI/地理编码/路径规划): https://restapi.amap.com/v3
#   Web服务(街景/高级功能):        https://restapi.amap.com/v4
#   AOI边界(高阶权限):            https://restapi.amap.com/v5
#
# 计费说明(2025年):
#   免费额度: 每个Key每日5000次调用
#   超出免费额度的功能按次计费 (见 https://lbs.amap.com/finance/price)
#   POI搜索: ¥0.01/次 (日配额10万次)
#   地理编码: ¥0.001/次
#   路径规划: ¥0.005/次
#   街景: 需单独计费，需申请权限
#   AOI边界: 高阶权限，单独计费
#
# 配额限制:
#   QPS限制(服务端): 30次/秒
#   单Key每日配额: 5000次 (免费用户)
#   批量请求请使用 delay 参数控制速率
#
# 坐标系要求:
#   所有输入输出坐标均为 GCJ-02 (高德坐标)
#   代码中对 WGS84 输入自动转换

class AmapBatchClient:
    """
    高德API批量请求管理器

    功能:
      - 多Key轮询（充分利用每个Key的免费配额）
      - 每日配额跟踪（避免超限）
      - QPS限速（避免触发服务端限流）
      - 自动重试（处理限流和偶发错误）
      - 断点续传（checkpoint机制）

    用法示例:
      client = AmapBatchClient(['your_key_1', 'your_key_2'])
      data = client.get('/v3/place/text', params={...})
    """

    # 高德API免费用户配额（Web服务Key: 500次/日；Web服务key有效期1天: 500总调用量）
    DAILY_QUOTA = 500
    QPS_LIMIT = 30           # 每秒最大请求数
    MIN_DELAY = 1.0 / QPS_LIMIT  # 最小请求间隔(秒)

    def __init__(
        self,
        keys: Union[str, List[str]],
        daily_quota: int = 5000,
        cache_dir: Path = None,
    ):
        """
        Args:
            keys: API Key (单字符串) 或 Key列表 (多Key轮询)
            daily_quota: 每个Key每日配额（免费用户5000，企业用户更高）
            cache_dir: 缓存目录（用于减少重复API调用）
        """
        if isinstance(keys, str):
            self.keys = [keys]
        else:
            self.keys = keys

        self.daily_quota = daily_quota
        self.cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

        # 配额跟踪（每个Key的当日已使用次数）
        self._usage: Dict[str, int] = {k: 0 for k in self.keys}
        self._key_idx = 0   # 当前轮询索引

        # Rate limiting: 上次请求时间戳
        self._last_request_time = 0.0

    # ── Key轮询 ──
    def _next_key(self) -> str:
        """取下一个可用Key（跳过配额用尽的Key）"""
        tried = 0
        while tried < len(self.keys):
            key = self.keys[self._key_idx]
            self._key_idx = (self._key_idx + 1) % len(self.keys)
            if self._usage[key] < self.daily_quota:
                return key
            tried += 1
        # 所有Key均耗尽，使用最后一个（降级处理）
        return self.keys[-1]

    # ── 速率控制 ──
    def _rate_limit(self):
        """QPS限速：确保请求间隔不小于 MIN_DELAY"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.MIN_DELAY:
            time.sleep(self.MIN_DELAY - elapsed)
        self._last_request_time = time.time()

    # ── HTTP请求 ──
    def get(
        self,
        endpoint: str,
        params: Dict,
        max_retries: int = 3,
    ) -> dict:
        """
        发送GET请求，自动处理轮询、限速、重试。

        Args:
            endpoint: API端点 (如 'v3/place/text')
            params: 请求参数（不含key，会自动填充）
            max_retries: 最大重试次数

        Returns:
            API响应dict，失败时返回空dict {}
        """
        import requests

        url = f"https://restapi.amap.com/{endpoint.lstrip('/')}"
        self._rate_limit()

        for attempt in range(max_retries):
            key = self._next_key()
            full_params = {**params, 'key': key}

            try:
                resp = requests.get(url, params=full_params, timeout=15)
                data = resp.json()

                # 成功
                if data.get('status') == '1' or data.get('info') == 'ok':
                    self._usage[key] += 1
                    return data

                # 配额耗尽，换Key重试
                info = data.get('info', '')
                if 'DAILY_QUERY_OVER_LIMIT' in info or 'QUOTE_EXCEED' in info:
                    self._usage[key] = self.daily_quota  # 标记为耗尽
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue

                # 其他错误
                print(f"  [高德] {endpoint}: {info} (attempt {attempt + 1})")
                return data

            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"  [高德网络错误] {endpoint}: {e}")
                    return {}
                time.sleep(1 << attempt)  # 指数退避

        return {}

    # ── 缓存 ──
    def cached_get(
        self,
        cache_key: str,
        endpoint: str,
        params: Dict,
        max_retries: int = 3,
    ) -> dict:
        """
        带文件缓存的GET请求 — 相同参数只请求一次。

        Args:
            cache_key: 缓存文件名（不含.json后缀）
            endpoint: API端点
            params: 请求参数
            max_retries: 最大重试次数
        """
        if self.cache_dir:
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception:
                    pass  # 缓存损坏，重新请求

        result = self.get(endpoint, params, max_retries)

        if self.cache_dir and result:
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return result

    def get_usage_report(self) -> Dict[str, int]:
        """获取当前各Key的使用量报告"""
        return dict(self._usage)

    def get_remaining_quota(self) -> int:
        """获取当前剩余可用配额总数"""
        return sum(self.daily_quota - u for u in self._usage.values())


# ============================================================================
# 高德API — POI查询
# ============================================================================
# POI分类编码（高德官方六位码）:
#   第1-2位: 大类 (01交通,05餐饮,06购物,07科教,08医疗,09商务,12风景名胜...)
#   第3-4位: 中类
#   第5-6位: 小类
#
# 研究相关分类:
#   050000 餐饮服务
#   060000 购物服务
#   060100 综合性市场
#   070000 科教文化服务
#   070300 高等教育（大学/学院）
#   070301 重点中学
#   070302 重点小学
#   070303 幼儿园
#   080000 医疗保健服务
#   080100 医院
#   080300 门诊部/卫生站/社康中心
#   090000 商业中心/商务住宅
#   090200 写字楼/产业园区
#   120000 商务住宅（住宅区/小区）
#   120100 住宅区/小区
#   120200 别墅
#   130000 风景名胜
#   130100 公园/广场
#   150000 交通设施服务
#   150200 长途汽车站
#   150203 公交车站
#   150500 地铁站
#   160000 金融服务
#   170000 政府机构及社会团体
#   170100 政府机关
#   170200 外国驻华机构

POI_CATEGORY_MAP: Dict[str, str] = {
    # 研究用分类（完整六位码，用于周边搜索types参数）
    'transit':        '150000',   # 交通设施服务
    'bus_stop':       '150203',   # 公交车站
    'subway':         '150500',   # 地铁站
    'education':      '070000',   # 科教文化
    'university':     '070300',   # 高等院校
    'primary_school': '070302',   # 重点小学
    'kindergarten':   '070303',   # 幼儿园
    'hospital':       '080100',   # 医院
    'clinic':         '080300',   # 社康/门诊
    'commerce':       '090000',   # 商业设施
    'office':         '090200',   # 写字楼/产业园
    'restaurant':     '050000',   # 餐饮服务
    'market':         '060100',   # 综合性市场
    'park':           '130100',   # 公园广场
    'bank':           '160000',   # 金融服务
    'residential':    '120000',   # 住宅区
    'government':     '170000',   # 政府机构
}

# 大类名称映射（用于反向查询）
POI_TYPE_NAME: Dict[str, str] = {v: k for k, v in POI_CATEGORY_MAP.items()}


class AMapPOIAPI:
    """
    高德地图 POI 查询封装

    功能:
      1. 关键字搜索 (place/text) — 按名称搜索特定POI
      2. 周边搜索 (place/around) — 获取某点周边半径内的POI（支持分页）
      3. 多边形搜索 (place/polygon) — 获取某个区域内的POI
      4. ID详情查询 (place/detail) — 获取POI详细信息

    使用建议:
      - 批量周边搜索使用 batch_around()，自动处理分页
      - 使用缓存减少重复请求: AmapBatchClient 会自动缓存
      - POI密度计算使用 calculate_poi_density()

    文档: https://lbs.amap.com/api/webservice/guide/api/newpoisearch
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    # ── 基础请求 ──

    def _normalize_poi(self, poi: dict) -> dict:
        """
        统一POI字段格式（GCJ-02坐标转为WGS84供内部使用）

        高德返回的location格式: "经度,纬度" (GCJ-02)
        转为: lng, lat (WGS84)
        """
        location = poi.get('location', '')
        lng_gcj, lat_gcj = None, None
        if location:
            parts = location.split(',')
            if len(parts) == 2:
                lng_gcj, lat_gcj = float(parts[0]), float(parts[1])

        if lng_gcj is not None:
            lng_wgs, lat_wgs = gcj02_to_wgs84(lng_gcj, lat_gcj)
        else:
            lng_wgs, lat_wgs = None, None

        return {
            'poi_id':      poi.get('id', ''),
            'poi_name':    poi.get('name', ''),
            'poi_type':    poi.get('type', ''),
            'typecode':    poi.get('typecode', ''),
            'address':     poi.get('address', ''),
            'lng_gcj02':   lng_gcj,
            'lat_gcj02':   lat_gcj,
            'lng_wgs84':   lng_wgs,
            'lat_wgs84':   lat_wgs,
            'distance':     float(poi.get('distance', 0) or 0),
        }

    # ── 关键字搜索 ──

    def search_by_keyword(
        self,
        keyword: str,
        city: str = '深圳',
        types: str = None,
        citylimit: bool = True,
        page_size: int = 25,
        max_pages: int = 20,
    ) -> List[dict]:
        """
        关键字搜索POI — 按名称搜索某城市内所有相关POI。

        适用场景:
          - 搜索某小区名称，获取其精确位置
          - 搜索"地铁站"获取南山区所有地铁站
          - 搜索城中村名称

        Args:
            keyword: 搜索关键字（只支持一个）
            city: 城市名/adcode/citycode
            types: POI六位分类码（可选，与keyword二选一）
            citylimit: 是否仅返回指定城市结果（建议True）
            page_size: 每页记录数（最大25）
            max_pages: 最大页数（超过返回数量会自动停止）

        Returns:
            POI列表，每项包含标准化字段
        """
        cache_key = f"kw_{hashlib.md5(f'{keyword}{city}{types}'.encode()).hexdigest()[:10]}"
        pois = []

        params = {
            'keywords': keyword,
            'city': city,
            'citylimit': str(citylimit).lower(),
            'offset': page_size,
            'page': 1,
            'extensions': 'all',
        }
        if types:
            params['types'] = types

        def fetch():
            fetched = []
            for page in range(1, max_pages + 1):
                paged_params = {**params, 'page': page}
                data = self.client.get('v3/place/text', paged_params)
                count = int(data.get('count', 0))
                pois_page = data.get('pois', [])
                for poi in pois_page:
                    fetched.append(self._normalize_poi(poi))

                if len(pois_page) < page_size or len(fetched) >= count:
                    break
                time.sleep(0.1)

            return fetched

        result = self.client.cached_get(
            cache_key=f"kw_{hashlib.md5(f'{keyword}{city}{types}'.encode()).hexdigest()[:10]}",
            endpoint='v3/place/text',
            params=params,
            max_retries=1,
        )
        if not result or result == {}:
            result = fetch()
        return result

    # ── 周边搜索 ──

    def search_around(
        self,
        lng: float,
        lat: float,
        radius: int = 500,
        types: str = None,
        keywords: str = None,
        sortrule: str = 'distance',
        page_size: int = 25,
        max_pages: int = 5,
    ) -> List[dict]:
        """
        周边搜索 — 获取指定坐标周边半径内的POI（支持多页自动翻页）。

        适用场景:
          - 计算某采样点500m内有多少公交站
          - 统计某城中村周边配套服务设施

        注意:
          - 输入坐标WGS84，内部自动转GCJ-02
          - 高德周边搜索默认按距离排序，最多返回100条
          - radius最大50000米，但实际有效范围受POI数量限制

        Args:
            lng, lat: 中心点坐标 (WGS84)
            radius: 搜索半径(米)，最大50000
            types: POI分类码，支持"|"分隔多类型
            keywords: 关键字（可选）
            sortrule: 排序规则 — 'distance'(按距离) 或 'weight'(综合排序)
            page_size: 每页记录数（最大25）
            max_pages: 最大页数（超过自动停止）

        Returns:
            POI列表
        """
        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
        cache_key = f"ar_{hashlib.md5(f'{gcj_lng:.5f}{gcj_lat:.5f}{radius}{types}'.encode()).hexdigest()[:10]}"

        base_params = {
            'location': f"{gcj_lng},{gcj_lat}",
            'radius': min(radius, 50000),
            'sortrule': sortrule,
            'offset': page_size,
            'page': 1,
            'extensions': 'all',
        }
        if types:
            base_params['types'] = types
        if keywords:
            base_params['keywords'] = keywords

        def fetch():
            fetched = []
            for page in range(1, max_pages + 1):
                paged_params = {**base_params, 'page': page}
                data = self.client.get('v3/place/around', paged_params)
                pois_page = data.get('pois', [])
                for poi in pois_page:
                    fetched.append(self._normalize_poi(poi))

                if len(pois_page) < page_size:
                    break
                time.sleep(0.1)

            return fetched

        result = self.client.cached_get(
            cache_key=cache_key,
            endpoint='v3/place/around',
            params=base_params,
            max_retries=1,
        )
        if not result or result == {}:
            result = fetch()
        return result

    # ── 多边形搜索 ──

    def search_polygon(
        self,
        polygon_coords: List[Tuple[float, float]],
        types: str = None,
        keywords: str = None,
        page_size: int = 25,
        max_pages: int = 20,
    ) -> List[dict]:
        """
        多边形搜索 — 获取闭合多边形区域内的所有POI。

        适用场景:
          - 获取南山区的所有公园
          - 获取某个城中村改造片区的所有POI

        Args:
            polygon_coords: 多边形顶点坐标列表 [(lng, lat), ...] WGS84
            types/keywords: 筛选条件
            page_size/max_pages: 分页控制
        """
        gcj_polygon = [wgs84_to_gcj02(lng, lat) for lng, lat in polygon_coords]
        polygon_str = '|'.join([f"{lng},{lat}" for lng, lat in gcj_polygon])
        cache_key = f"poly_{hashlib.md5(polygon_str.encode()).hexdigest()[:10]}"

        base_params = {
            'polygon': polygon_str,
            'offset': page_size,
            'page': 1,
            'extensions': 'all',
        }
        if types:
            base_params['types'] = types
        if keywords:
            base_params['keywords'] = keywords

        def fetch():
            fetched = []
            for page in range(1, max_pages + 1):
                paged_params = {**base_params, 'page': page}
                data = self.client.get('v3/place/polygon', paged_params)
                pois_page = data.get('pois', [])
                for poi in pois_page:
                    fetched.append(self._normalize_poi(poi))

                if len(pois_page) < page_size:
                    break
                time.sleep(0.1)

            return fetched

        result = self.client.cached_get(
            cache_key=cache_key,
            endpoint='v3/place/polygon',
            params=base_params,
            max_retries=1,
        )
        if not result or result == {}:
            result = fetch()
        return result

    # ── POI详情 ──

    def get_poi_detail(
        self,
        poi_id: str,
    ) -> Optional[dict]:
        """
        POI ID详情查询 — 获取某个POI的详细信息。

        适用场景:
          - 获取小区的入口/出口坐标
          - 获取POI的完整地址和联系方式
          - 结合AOI边界API获取精确边界
        """
        cache_key = f"detail_{poi_id}"

        def fetch():
            data = self.client.get('v3/place/detail', {'id': poi_id})
            pois = data.get('pois', [])
            if pois:
                return self._normalize_poi(pois[0])
            return None

        result = self.client.cached_get(cache_key, 'v3/place/detail', {}, max_retries=2)
        if not result or 'pois' not in result or not result['pois']:
            result = fetch()
        return result

    # ── 批量周边搜索 ──

    def batch_around(
        self,
        points: List[Tuple[float, float]],
        radius: int = 500,
        types: str = None,
        delay: float = 0.15,
        progress: bool = True,
    ) -> Dict[Tuple[float, float], List[dict]]:
        """
        批量对多个点进行周边POI搜索。

        Args:
            points: 坐标列表 [(lng, lat), ...] WGS84
            radius: 搜索半径(米)
            types: POI分类码
            delay: 请求间隔(秒)，建议0.1-0.2
            progress: 是否打印进度

        Returns:
            { (lng, lat): [poi_list] }
        """
        results = {}
        total = len(points)

        if progress:
            print(f"[POI批量] {total} 个点 (r={radius}m)...")

        for i, (lng, lat) in enumerate(points):
            pois = self.search_around(lng, lat, radius=radius, types=types)
            results[(lng, lat)] = pois

            if progress and (i + 1) % 20 == 0:
                print(f"\r[POI批量] {i + 1}/{total} ({100 * (i + 1) / total:.0f}%)", end='', flush=True)

            time.sleep(delay)

        if progress:
            print()
        return results

    # ── POI密度分析 ──

    def calculate_poi_density(
        self,
        sample_df: pd.DataFrame,
        radii: List[int] = [100, 300, 500],
        poi_types: List[str] = None,
        delay: float = 0.12,
    ) -> pd.DataFrame:
        """
        计算每个采样点的POI密度与多样性指标。

        新增研究核心指标（15分钟城市假说验证）:
          - Shannon-Wiener多样性指数: H = -Σ(p_i × ln(p_i))
          - Evenness均匀度指数: E = H / H_max（取值0~1，越接近1越均衡）
          - 日常生活设施比率: (公交+社康+菜市场) / 总POI数
          - 服务设施加权密度: 权重×距离衰减的POI数量

        Args:
            sample_df: 采样点DataFrame
            radii: 搜索半径列表(米)
            poi_types: POI类型列表
            delay: 请求间隔(秒)

        Returns:
            追加了POI密度+多样性指标的DataFrame
        """
        if poi_types is None:
            poi_types = ['transit', 'bus_stop', 'education', 'hospital',
                          'clinic', 'commerce', 'restaurant', 'park', 'residential']

        type_codes = [POI_CATEGORY_MAP.get(t, t) for t in poi_types]
        types_str = '|'.join(type_codes)

        # 日常必需设施类型（用于计算日常生活设施比率）
        ESSENTIAL_TYPES = {'transit', 'bus_stop', 'clinic', 'market'}

        df = sample_df.copy()
        coords = list(zip(df['lng'], df['lat']))

        for radius in radii:
            print(f"[POI密度] 半径={radius}m 查询...")
            all_records = []

            for i, (lng, lat) in enumerate(coords):
                pois = self.search_around(lng, lat, radius=radius, types=types_str)
                base_counts = {t: 0 for t in poi_types}
                base_counts['_total'] = 0

                # 按分类码精确匹配
                type_counts = {t: 0 for t in poi_types}
                for poi in pois:
                    tc = poi.get('typecode', '')[:6]
                    for t_name, t_code in POI_CATEGORY_MAP.items():
                        if t_name in type_counts and tc.startswith(t_code[:2]):
                            type_counts[t_name] += 1
                            break

                # ── Shannon-Wiener 多样性指数 ──
                total = sum(type_counts.values())
                h_shannon = 0.0
                if total > 0:
                    for cnt in type_counts.values():
                        p = cnt / total
                        if p > 0:
                            h_shannon -= p * math.log(p)

                # ── Evenness 均匀度指数 ──
                n_types = len([c for c in type_counts.values() if c > 0])
                h_max = math.log(n_types) if n_types > 1 else 0
                h_evenness = h_shannon / h_max if h_max > 0 else 0

                # ── 日常生活设施比率 ──
                essential_cnt = sum(type_counts.get(t, 0) for t in ESSENTIAL_TYPES)
                essential_ratio = essential_cnt / total if total > 0 else 0

                # ── POI密度(个/km²) ──
                area_km2 = math.pi * (radius / 1000) ** 2
                poi_density = total / area_km2

                # ── 合成记录 ──
                record = {'_total': total, **{f'{k}_cnt': v for k, v in type_counts.items()}}
                record['_shannon'] = round(h_shannon, 4)
                record['_evenness'] = round(h_evenness, 4)
                record['_essential_ratio'] = round(essential_ratio, 4)
                record['_density'] = round(poi_density, 2)
                all_records.append(record)

                if (i + 1) % 20 == 0:
                    print(f"\r  进度 {i + 1}/{len(coords)} ({100 * (i + 1) / len(coords):.0f}%)",
                          end='', flush=True)
                time.sleep(delay)

            print()
            # 展平到DataFrame列
            rec_df = pd.DataFrame(all_records)
            for col in rec_df.columns:
                df[f'poi_{radius}m_{col}'] = rec_df[col].values

        return df



# ============================================================================
# 高德API — AOI边界查询
# ============================================================================
# AOI (Area of Interest) = 具有面状区域特点的POI
# 包括: 小区、校园、公园、景区、工业园区、商场、医院、火车站等
#
# 注意: AOI边界查询(v5/aoi/polyline)是 高阶权限，需工单申请开通
# 普通POI搜索权限无法使用此接口
#
# 申请方式: https://lbs.amap.com/ -> 控制台 -> 工单 -> 申请高阶服务

class AMapAOIAPI:
    """
    高德地图 AOI (Area of Interest) 边界查询

    功能:
      - get_aoi_boundary: 通过POI ID获取精确边界多边形
      - search_and_get_boundary: 先搜索再批量获取边界

    适用场景:
      - 城中村边界量化（用于计算SCR）
      - 高端小区边界叠加分析
      - 步行指数(EWW)计算时的面状区域处理

    权限要求:
      - 需要 AOI边界查询 高阶权限（工单申请）
      - 无权限时 get_aoi_boundary 返回 None
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    def get_aoi_boundary(self, poi_id: str) -> Optional[List[Tuple[float, float]]]:
        """
        通过POI ID查询AOI边界多边形。

        返回坐标为 WGS84（内部从GCJ-02转换）。

        Args:
            poi_id: POI ID（可从POI搜索结果的 poi_id 字段获取）

        Returns:
            边界坐标列表 [(lng, lat), ...] WGS84
            None = 无权限或查询失败
        """
        cache_key = f"aoi_{poi_id}"
        cache_file = (self.client.cache_dir / f"{cache_key}.json") if self.client.cache_dir else None

        if cache_file and cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data and data != 'NO_PERMISSION':
                        return [tuple(p) for p in data]
            except Exception:
                pass

        data = self.client.get('v5/aoi/polyline', {'id': poi_id})

        if data.get('status') != '0':
            print(f"  [AOI] 权限不足或查询失败: poi_id={poi_id}, info={data.get('info')}")
            if cache_file:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump('NO_PERMISSION', f)
            return None

        aois = data.get('aois', [])
        if not aois:
            return None

        polyline_str = aois[0].get('polyline', '')
        if not polyline_str:
            return None

        # polyline格式: "lng,lat_lng,lat_..." (GCJ-02，下划线分隔)
        gcj_coords = [
            tuple(map(float, pt.split(',')))
            for pt in polyline_str.split('_') if pt
        ]
        wgs84_coords = [gcj02_to_wgs84(lng, lat) for lng, lat in gcj_coords]

        if cache_file:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump([[lng, lat] for lng, lat in wgs84_coords], f, ensure_ascii=False)

        return wgs84_coords

    def search_aoi_in_area(
        self,
        area_coords: List[Tuple[float, float]],
        keywords: str = None,
        types: str = '120100',
    ) -> List[dict]:
        """
        在某个区域内搜索AOI类型POI并获取其边界。

        适用场景:
          - 获取南山区所有住宅小区的边界
          - 获取城中村片区的精确边界

        Args:
            area_coords: 区域多边形 [(lng, lat), ...] WGS84
            keywords: 关键字筛选
            types: POI分类码，默认120100(住宅区)

        Returns:
            [{poi_info, boundary_coords}, ...]
        """
        pois = []
        poi_api = AMapPOIAPI(self.client.keys[0], cache_dir=self.client.cache_dir)
        all_pois = poi_api.search_polygon(area_coords, types=types, keywords=keywords)

        for poi in all_pois:
            boundary = self.get_aoi_boundary(poi['poi_id'])
            pois.append({**poi, 'boundary_wgs84': boundary})

        return pois


# ============================================================================
# 高德API — 地理编码与逆地理编码
# ============================================================================
# 地理编码: 地址 → 坐标 (geocode)
# 逆地理编码: 坐标 → 地址 (regeo)
#
# 计费: ¥0.001/次（极低成本，建议批量使用）

class AMapGeocodingAPI:
    """
    高德地图 地理编码 / 逆地理编码 API

    功能:
      1. geocode: 地址 → GCJ-02坐标
      2. regeocode: GCJ-02坐标 → 结构化地址
      3. batch_geocode: 批量地址转坐标（带缓存）

    适用场景:
      - 已知城中村名称，查询其精确坐标（用于采样验证）
      - 采样点逆编码后获取结构化地址（用于报告）
      - 研究区范围定位（地址→坐标）
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    def geocode(self, address: str, city: str = '深圳') -> Optional[dict]:
        """
        地理编码: 将地址转换为坐标

        Args:
            address: 详细地址（如"南山区桃源街道塘朗村"）
            city: 城市限定

        Returns:
            {
                'province', 'city', 'district', 'location': (lng_gcj, lat_gcj),
                'level' (匹配等级: 省/市/区/街/门牌号)
            }
        """
        cache_key = f"geo_{hashlib.md5(f'{address}{city}'.encode()).hexdigest()[:10]}"

        def fetch():
            data = self.client.get('v3/geocode/geocode', {
                'address': address,
                'city': city,
            })
            geocodes = data.get('geocodes', [])
            if geocodes:
                g = geocodes[0]
                loc = g.get('location', '').split(',')
                if len(loc) == 2:
                    return {
                        'province': g.get('province', ''),
                        'city':     g.get('city', ''),
                        'district':  g.get('district', ''),
                        'lng_gcj':   float(loc[0]),
                        'lat_gcj':   float(loc[1]),
                        'level':     g.get('level', ''),
                    }
            return None

        result = self.client.cached_get(cache_key, 'v3/geocode/geocode', {}, max_retries=1)
        if not result or 'geocodes' not in result:
            result = fetch()
        return result

    def regeocode(
        self,
        lng: float,
        lat: float,
        radius: int = 200,
        extensions: str = 'base',
    ) -> Optional[dict]:
        """
        逆地理编码: 将坐标转换为结构化地址

        Args:
            lng, lat: GCJ-02坐标（输入WGS84会自动转换）
            radius: 逆地理编码半径(米)，默认200
            extensions: 'base'(仅基本信息) 或 'all'(包含最近POI/道路)

        Returns:
            {
                'formatted_address': '广东省深圳市南山区...',
                'province', 'city', 'district', 'township',
                'street', 'number',  # 门牌号
                'pois': [...]        # extensions='all'时包含附近POI
            }
        """
        # 支持WGS84输入
        if not self._is_gcj02(lng, lat):
            lng, lat = wgs84_to_gcj02(lng, lat)

        cache_key = f"regeo_{hashlib.md5(f'{lng:.5f}{lat:.5f}{radius}'.encode()).hexdigest()[:10]}"

        def fetch():
            data = self.client.get('v3/geocode/regeo', {
                'location': f"{lng},{lat}",
                'radius': radius,
                'extensions': extensions,
                'batch': 'false',
            })
            regeocodes = data.get('regeocodes', [])
            if regeocodes:
                r = regeocodes[0]
                return {
                    'formatted_address': r.get('formatted_address', ''),
                    'province':  r.get('province', ''),
                    'city':      r.get('city', ''),
                    'district':  r.get('district', ''),
                    'township':  r.get('township', ''),
                    'street':    r.get('streetNumber', {}).get('street', ''),
                    'number':    r.get('streetNumber', {}).get('number', ''),
                    'pois':      r.get('pois', []) if extensions == 'all' else [],
                }
            return None

        result = self.client.cached_get(cache_key, 'v3/geocode/regeo', {}, max_retries=1)
        if not result or 'formatted_address' not in result:
            result = fetch()
        return result

    @staticmethod
    def _is_gcj02(lng: float, lat: float) -> bool:
        """粗略判断是否为GCJ-02坐标（中国范围内WGS84与GCJ-02偏差约50-500m）"""
        return abs(lng - 113.9) < 0.01 and abs(lat - 22.5) < 0.01

    def batch_regeocode(
        self,
        coords: List[Tuple[float, float]],
        radius: int = 200,
        delay: float = 0.1,
    ) -> List[dict]:
        """
        批量逆地理编码（带缓存）

        Returns:
            List[dict] — 与输入coords对应，失败项为None
        """
        results = []
        for lng, lat in coords:
            results.append(self.regeocode(lng, lat, radius=radius))
            time.sleep(delay)
        return results


# ============================================================================
# 高德API — 行政区划查询
# ============================================================================
# 功能: 查询行政区划边界（用于获取精确的研究区范围）
# 计费: ¥0.001/次

class AMapDistrictAPI:
    """
    高德地图 行政区划 API

    功能:
      - get_district_boundary: 获取某级行政区划的边界
      - get_nanshan_boundary: 获取南山区精确边界（预设）

    适用场景:
      - 自动获取南山区精确边界（替代手动BOUNDS配置）
      - 城中村/社区所在街道识别
      - 研究区采样时的边界裁切
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    def get_district_boundary(
        self,
        adcode: str,
        extensions: str = 'all',
    ) -> Optional[dict]:
        """
        获取行政区划边界

        Args:
            adcode: 行政区划代码
                440305 = 南山区
                440300 = 深圳市
                440000 = 广东省
            extensions: 'base'(仅中心点) 或 'all'(含边界)

        Returns:
            {
                'name': '南山区',
                'adcode': '440305',
                'center': (lng_gcj, lat_gcj),
                'polyline': [(lng_wgs, lat_wgs), ...]  # extensions='all'时
            }
        """
        cache_key = f"district_{adcode}_{extensions}"

        def fetch():
            data = self.client.get('v3/config/district', {
                'keywords': adcode,
                'subdistrict': '0',
                'extensions': extensions,
            })
            districts = data.get('districts', [])
            if districts:
                d = districts[0]
                center = d.get('center', '').split(',')
                result = {
                    'name': d.get('name', ''),
                    'adcode': d.get('adcode', adcode),
                    'center': (float(center[0]), float(center[1])) if len(center) == 2 else None,
                }
                if extensions == 'all':
                    polyline_str = d.get('polyline', '')
                    if polyline_str:
                        gcj_pts = [
                            tuple(map(float, pt.split(',')))
                            for pt in polyline_str.split(';') if pt
                        ]
                        result['polyline_wgs84'] = [gcj02_to_wgs84(lng, lat) for lng, lat in gcj_pts]
                    else:
                        result['polyline_wgs84'] = []
                return result
            return None

        result = self.client.cached_get(cache_key, 'v3/config/district', {}, max_retries=2)
        if not result or 'name' not in result:
            result = fetch()
        return result

    def get_nanshan_boundary(self) -> Optional[dict]:
        """获取深圳市南山区的精确边界（预设440305）"""
        return self.get_district_boundary('440305', extensions='all')


# ============================================================================
# 高德API — 天气预报
# ============================================================================
# 功能: 查询实时/预报天气数据
# 计费: ¥0.001/次
# 注意: 高德天气API返回的是基础天气，无空气质量数据

class AMapWeatherAPI:
    """
    高德地图 天气 API

    功能:
      - get_weather: 获取指定城市/区域的实时/预报天气
      - batch_weather: 批量获取多个区域的天气

    适用场景:
      - 采集时的环境因素记录（如: 雨天/晴天/PM2.5）
      - 天气-可达性关联分析
      - 采样时间的气象条件标注

    注意:
      - 高德天气是基础天气（温度/湿度/风速/天气描述）
      - 无空气质量数据（需另行查询）
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    def get_weather(
        self,
        city_or_adcode: str = '440305',
        extensions: str = 'all',
    ) -> Optional[dict]:
        """
        获取天气预报

        Args:
            city_or_adcode: 城市名或adcode (默认 南山区=440305)
            extensions: 'base'(实时天气) 或 'all'(+预报)

        Returns:
            {
                'province', 'city', 'adcode',
                'report_time': '2025-01-15 14:30:00',
                'casts': [  # extensions='all'时
                    {'date', 'week', 'day_weather', 'night_weather',
                     'day_temp', 'night_temp', 'day_wind', 'night_wind',
                     'day_power', 'night_power'},
                    ...
                ]
            }
        """
        cache_key = f"weather_{city_or_adcode}_{extensions}"

        def fetch():
            data = self.client.get('v3/weather/weatherInfo', {
                'city': city_or_adcode,
                'extensions': extensions,
            })
            if data.get('status') == '1':
                lives = data.get('lives', [])
                casts = data.get('forecasts', [])
                result = {}
                if lives:
                    l = lives[0]
                    result.update({
                        'province': l.get('province', ''),
                        'city':     l.get('city', ''),
                        'adcode':   l.get('adcode', ''),
                        'weather':   l.get('weather', ''),
                        'temperature': l.get('temperature', ''),
                        'wind':      l.get('winddirection', ''),
                        'wind_power': l.get('windpower', ''),
                        'humidity':  l.get('humidity', ''),
                        'report_time': l.get('reporttime', ''),
                    })
                if casts:
                    result['casts'] = casts[0].get('cast', [])
                return result
            return None

        result = self.client.cached_get(cache_key, 'v3/weather/weatherInfo', {}, max_retries=2)
        if not result:
            result = fetch()
        return result


# ============================================================================
# 高德API — 路径规划 (15分钟城市核心指标)
# ============================================================================
# 功能: 步行/公交/驾车路线规划
# 步行规划: ¥0.005/次
# 驾车规划: ¥0.005/次
# 公交规划: ¥0.01/次
#
# 15分钟城市核心指标计算:
#   从采样点出发，搜索15分钟内可达的最大范围
#   对比理论15分钟可达范围，评估"可达性幻觉"

class AMapDirectionAPI:
    """
    高德地图 路径规划 API

    功能:
      - walking_isochrone: 步行等时圈分析（15分钟可达范围）
      - walking_route: 步行路线规划
      - transit_route: 公交路线规划

    15分钟城市研究应用:
      - 计算每个采样点的"15分钟可达面积"
      - 与理论圆形面积对比，得到"面积比值"(AII)
      - 叠加城中村/高端社区分类，分析可达性差异
    """

    def __init__(self, key: Union[str, List[str]], cache_dir: Path = None):
        self.client = AmapBatchClient(key, cache_dir=cache_dir)

    def walking_isochrone(
        self,
        lng: float,
        lat: float,
        time_minutes: int = 15,
    ) -> Optional[dict]:
        """
        步行等时圈 — 计算从某点出发N分钟内可达的最大范围与关键指标。

        这是15分钟城市研究的核心API。

        Returns:
            {
                'boundary': 等时圈边界坐标列表 [(lng, lat), ...] WGS84
                'total_distance_m': 15分钟最大步行距离(米)
                'total_duration_s': 最优路径总时长(秒)
                'reachable_roads': 经过的道路数量
                'area_km2_est': 等时圈面积估算(km²，用路径覆盖范围的凸包)
            }
            None = 规划失败
        """
        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
        params = {
            'origin': f"{gcj_lng},{gcj_lat}",
            'extensions': 'all',
        }
        cache_key = f"iso_{hashlib.md5(f'{gcj_lng:.5f}{gcj_lat:.5f}{time_minutes}'.encode()).hexdigest()[:10]}"

        def fetch():
            data = self.client.get('v3/direction/walking', params)
            routes = data.get('paths', [])
            if not routes:
                return None

            # 取最优路径
            best = min(routes, key=lambda r: float(r.get('duration', 999999)))
            total_distance = int(best.get('distance', 0))
            total_duration = int(best.get('duration', 0))
            steps = best.get('steps', [])

            # 提取所有途经点（等时圈近似边界）
            boundary = [(gcj_lng, gcj_lat)]
            reachable_roads = len(steps)
            cum_time = 0
            all_lngs, all_lats = [gcj_lng], [gcj_lat]

            for step in steps:
                step_time = int(step.get('duration', 0))
                if cum_time + step_time > time_minutes * 60:
                    break
                cum_time += step_time
                # 从step的polyline提取途经点
                polyline = step.get('polyline', '')
                if polyline:
                    for pt in polyline.split(';'):
                        if ':' in pt:
                            p_lng, p_lat = pt.split(':')
                            all_lngs.append(float(p_lng))
                            all_lats.append(float(p_lat))
                            boundary.append((float(p_lng), float(p_lat)))

            # 转换为WGS84
            boundary_wgs = [gcj02_to_wgs84(b[0], b[1]) for b in boundary]

            # 面积估算：用路径起终点连线距离×平均宽度(500m)近似
            if len(boundary) >= 2:
                last = boundary[-1]
                straight_dist = math.sqrt((last[0] - gcj_lng)**2 + (last[1] - gcj_lat)**2) * 111000
                area_est = straight_dist * 0.5  # km²（粗略估计）
            else:
                area_est = 0.0

            return {
                'boundary': boundary_wgs,
                'total_distance_m': total_distance,
                'total_duration_s': total_duration,
                'reachable_roads': reachable_roads,
                'area_km2_est': round(area_est, 4),
                'origin_lng': lng,
                'origin_lat': lat,
            }

        result = self.client.cached_get(
            cache_key=cache_key,
            endpoint='v3/direction/walking',
            params=params,
            max_retries=2,
        )
        if not result or result == {}:
            result = fetch()
        return result

    def walking_route(
        self,
        origin_lng: float,
        origin_lat: float,
        dest_lng: float,
        dest_lat: float,
    ) -> Optional[dict]:
        """
        步行路线规划 — 计算两点间的步行路线及时间/距离。

        Args:
            origin_*/dest_*: 起终点坐标 (WGS84)

        Returns:
            {
                'distance_m': 总距离(米),
                'duration_s': 总时间(秒),
                'steps': [{'instruction', 'distance', 'duration', 'road'}, ...]
            }
        """
        o_gcj = wgs84_to_gcj02(origin_lng, origin_lat)
        d_gcj = wgs84_to_gcj02(dest_lng, dest_lat)
        cache_key = f"walk_{hashlib.md5(f'{o_gcj[0]:.5f}{o_gcj[1]:.5f}{d_gcj[0]:.5f}{d_gcj[1]:.5f}'.encode()).hexdigest()[:10]}"

        def fetch():
            data = self.client.get('v3/direction/walking', {
                'origin': f"{o_gcj[0]},{o_gcj[1]}",
                'destination': f"{d_gcj[0]},{d_gcj[1]}",
            })
            paths = data.get('paths', [])
            if paths:
                p = paths[0]
                steps = p.get('steps', [])
                return {
                    'distance_m': int(p.get('distance', 0)),
                    'duration_s': int(p.get('duration', 0)),
                    'steps': [
                        {
                            'instruction': s.get('instruction', ''),
                            'road': s.get('road', ''),
                            'distance': int(s.get('distance', 0)),
                            'duration': int(s.get('duration', 0)),
                        }
                        for s in steps
                    ],
                }
            return None

        params = {
            'origin': f"{o_gcj[0]},{o_gcj[1]}",
            'destination': f"{d_gcj[0]},{d_gcj[1]}",
        }
        result = self.client.cached_get(
            cache_key=cache_key,
            endpoint='v3/direction/walking',
            params=params,
            max_retries=2,
        )
        if not result or result == {}:
            result = fetch()
        return result


# ============================================================================
# 影像质量过滤
# ============================================================================
# 街景影像质量评估维度:
#   1. 文件大小 — 过小(如<5KB)通常是API返回了错误占位图
#   2. 文件完整性 — JPEG魔数验证、EOF标记
#   3. 亮度/对比度 — 过暗(如夜间/隧道)或过曝图像不适合分析
#   4. 尺寸 — 分辨率低于阈值(如宽<300px)则无法用于深度学习模型
#   5. 清晰度 — Laplacian方差评估（OpenCV）

class ImageQualityFilter:
    """
    街景影像质量过滤器

    在正式采集完成后，对所有已采集影像进行质量评估，
    自动删除不合格影像（过小/损坏/过暗/模糊），保留清晰可用的数据。

    质量指标:
      - 文件大小 (size_bytes)
      - 亮度均值 (mean_brightness)
      - 对比度 (std_brightness)
      - 清晰度 (laplacian_var)
      - 有效像素比 (valid_ratio)

    删除标准(可配置):
      - 文件大小 < min_file_size
      - 亮度均值 < min_brightness 或 > max_brightness
      - 清晰度(laplacian) < min_sharpness
      - 有效像素比 < min_valid_ratio
    """

    def __init__(
        self,
        min_file_size: int = 5000,
        min_brightness: float = 20.0,
        max_brightness: float = 230.0,
        min_sharpness: float = 50.0,
        min_valid_ratio: float = 0.3,
    ):
        """
        Args:
            min_file_size: 文件最小字节数(字节)，低于此值视为无效
            min_brightness: 最小亮度均值(0-255)，过暗图像(如夜间/隧道)会被删除
            max_brightness: 最大亮度均值(0-255)，过曝图像会被删除
            min_sharpness: 最小拉普拉斯方差(清晰度)，低于此值视为模糊
            min_valid_ratio: 有效像素比下限(非全黑/全白区域)
        """
        self.min_file_size = min_file_size
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_sharpness = min_sharpness
        self.min_valid_ratio = min_valid_ratio

    def check_file_integrity(self, filepath: Path) -> dict:
        """
        检查单个影像文件的质量指标。

        Returns:
            {
                'filepath': Path,
                'size_bytes': int,
                'valid': bool,          # 是否通过所有检查
                'reasons': [str],       # 失败原因列表
                'laplacian_var': float,  # 清晰度
                'mean_brightness': float,  # 亮度均值
                'std_brightness': float,   # 亮度标准差
                'valid_ratio': float,       # 有效像素比
            }
        """
        import cv2

        result = {
            'filepath': filepath,
            'size_bytes': 0,
            'valid': False,
            'reasons': [],
            'laplacian_var': 0.0,
            'mean_brightness': 0.0,
            'std_brightness': 0.0,
            'valid_ratio': 1.0,
        }

        # ── 1. 文件存在性 ──
        if not filepath.exists():
            result['reasons'].append('file_not_exists')
            return result

        # ── 2. 文件大小 ──
        size = filepath.stat().st_size
        result['size_bytes'] = size
        if size < self.min_file_size:
            result['reasons'].append(f'file_too_small({size}B < {self.min_file_size}B)')
            return result

        # ── 3. JPEG魔数验证 ──
        try:
            with open(filepath, 'rb') as f:
                header = f.read(3)
                # JPEG: FF D8 FF, PNG: 89 50 4E
                if header[:2] != b'\xff\xd8':
                    result['reasons'].append(f'not_jpeg(header={header.hex()})')
                    return result
        except Exception:
            result['reasons'].append('read_header_failed')
            return result

        # ── 4. OpenCV质量分析 ──
        try:
            img = cv2.imread(str(filepath))
            if img is None:
                result['reasons'].append('opencv_read_failed')
                return result

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape

            # 亮度统计
            mean_b = float(gray.mean())
            std_b = float(gray.std())
            result['mean_brightness'] = mean_b
            result['std_brightness'] = std_b

            if mean_b < self.min_brightness:
                result['reasons'].append(f'too_dark({mean_b:.1f} < {self.min_brightness})')
                return result
            if mean_b > self.max_brightness:
                result['reasons'].append(f'too_bright({mean_b:.1f} > {self.max_brightness})')
                return result

            # 清晰度(Laplacian方差)
            lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            result['laplacian_var'] = lap_var
            if lap_var < self.min_sharpness:
                result['reasons'].append(f'too_blurry(lap={lap_var:.1f} < {self.min_sharpness})')
                return result

            # 有效像素比(排除全黑/全白)
            valid_pixels = np.sum((gray > 5) & (gray < 250))
            total_pixels = h * w
            valid_ratio = valid_pixels / total_pixels
            result['valid_ratio'] = valid_ratio
            if valid_ratio < self.min_valid_ratio:
                result['reasons'].append(f'invalid_content(ratio={valid_ratio:.2f} < {self.min_valid_ratio})')
                return result

            # 全部通过
            result['valid'] = True

        except Exception as e:
            result['reasons'].append(f'opencv_error({e})')

        return result

    def filter_directory(
        self,
        image_dir: Path,
        extensions: List[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        对指定目录下所有影像进行质量过滤。

        Args:
            image_dir: 影像目录
            extensions: 要检查的文件扩展名，默认 ['jpg', 'jpeg', 'png']
            dry_run: True=只分析不删除，False=删除不合格影像

        Returns:
            {
                'total': int,
                'valid': int,
                'deleted': int,
                'stats': {laplacian/mean_brightness/...的统计},
                'deleted_files': [filepath, ...],
                'valid_files': [filepath, ...],
            }
        """
        if extensions is None:
            extensions = ['jpg', 'jpeg', 'png', 'JPG', 'JPEG', 'PNG']

        print(f"[质量过滤] {'(dry-run, 不删除)' if dry_run else ''}检查目录: {image_dir}")

        image_files = []
        for ext in extensions:
            image_files.extend(image_dir.rglob(f'*.{ext}'))

        if not image_files:
            print("[质量过滤] 目录为空，跳过")
            return {'total': 0, 'valid': 0, 'deleted': 0, 'deleted_files': [], 'valid_files': []}

        print(f"[质量过滤] 共 {len(image_files)} 个影像，开始质量评估...")

        valid_files = []
        deleted_files = []
        all_stats = {'laplacian': [], 'brightness': [], 'std': [], 'valid_ratio': []}

        for fp in image_files:
            info = self.check_file_integrity(fp)
            if info['valid']:
                valid_files.append(fp)
                all_stats['laplacian'].append(info['laplacian_var'])
                all_stats['brightness'].append(info['mean_brightness'])
                all_stats['std'].append(info['std_brightness'])
                all_stats['valid_ratio'].append(info['valid_ratio'])
            else:
                deleted_files.append(fp)
                if not dry_run:
                    try:
                        fp.unlink()
                    except Exception as e:
                        print(f"  [删除失败] {fp.name}: {e}")
                reason = info['reasons'][0] if info['reasons'] else 'unknown'
                print(f"  [不合格] {fp.name}: {reason} (size={info['size_bytes']}, lap={info['laplacian_var']:.1f}, bright={info['mean_brightness']:.1f})")

        stats_summary = {
            'laplacian_mean': float(np.mean(all_stats['laplacian'])) if all_stats['laplacian'] else 0,
            'brightness_mean': float(np.mean(all_stats['brightness'])) if all_stats['brightness'] else 0,
            'valid_ratio_mean': float(np.mean(all_stats['valid_ratio'])) if all_stats['valid_ratio'] else 0,
        }

        result = {
            'total': len(image_files),
            'valid': len(valid_files),
            'deleted': len(deleted_files),
            'valid_files': valid_files,
            'deleted_files': deleted_files,
            'stats': stats_summary,
        }

        print(f"[质量过滤] 完成: 总数={result['total']}, 合格={result['valid']}, "
              f"删除={result['deleted']}, 合格率={100*result['valid']/max(result['total'],1):.1f}%")
        print(f"[质量过滤] 平均清晰度={stats_summary['laplacian_mean']:.1f}, "
              f"平均亮度={stats_summary['brightness_mean']:.1f}")

        return result


# ============================================================================
# 高德API — 静态地图影像采集
# ============================================================================
# 高德静态地图API (v3/staticmap)
# 文档: https://lbs.amap.com/api/webservice/guide/api/staticmaps
#
# 功能:
#   - 返回地图图片（可带标注/标签/折线覆盖物）
#   - 支持普通图(scale=1)和高清图(scale=2, 宽高各翻倍, zoom+1)
#   - 最大尺寸 1024×1024，标注/标签/折线各最多10/10/4个
#
# 配额: Web服务Key 500次/日（有效期1天的Key总量500次）
#
# 典型URL示例:
#   https://restapi.amap.com/v3/staticmap?
#     location=116.481485,39.990464
#     &zoom=15
#     &size=600*400
#     &markers=mid,,A:116.481485,39.990464
#     &paths=5,0xFF0000,1,,:116.48,39.99;116.49,40.00
#     &key=<YOUR_KEY>

class AmapStaticMapAPI:
    """
    高德静态地图API封装

    用法示例:
      # 单点静态地图
      api = AmapStaticMapAPI('YOUR_KEY')
      path, meta = api.get_image(lng=113.93, lat=22.54, zoom=16)

      # 带采样点标注
      api = AmapStaticMapAPI('YOUR_KEY')
      path, meta = api.get_image(
          lng=113.93, lat=22.54, zoom=15,
          markers=[(113.93, 22.54, 'A', 'red')],
      )

      # 带步行路径（15分钟等时圈）
      api = AmapStaticMapAPI('YOUR_KEY')
      path, meta = api.get_image(
          lng=113.93, lat=22.54, zoom=15,
          markers=[(113.93, 22.54, 'A', 'red')],
          paths=[([...polygon_coords...], 'blue')],
      )

      # 批量采集（断点续传）
      df_result = api.batch_collect(sample_df, output_dir)
    """

    BASE_URL = "https://restapi.amap.com/v3/staticmap"

    # 内置颜色名称 → 0xRRGGBB格式
    COLOR_MAP: Dict[str, str] = {
        'red':    '0xFF0000',
        'blue':   '0x0000FF',
        'green':  '0x008000',
        'yellow': '0xFFFF00',
        'orange': '0xFFA500',
        'purple': '0x800080',
        'gray':   '0x808080',
        'white':  '0xFFFFFF',
        'black':  '0x000000',
    }

    def __init__(self, key: Union[str, List[str]]):
        if isinstance(key, str):
            self.keys = [key]
        else:
            self.keys = key
        self._key_idx = 0
        self._usage: Dict[str, int] = {k: 0 for k in self.keys}

    def _next_key(self) -> str:
        n = len(self.keys)
        for _ in range(n):
            k = self.keys[self._key_idx]
            self._key_idx = (self._key_idx + 1) % n
            if self._usage[k] < 500:
                return k
        return self.keys[-1]

    def _format_color(self, color: str) -> str:
        if color in self.COLOR_MAP:
            return self.COLOR_MAP[color]
        if color.startswith('0x') and len(color) == 8:
            return color
        return '0xFF0000'

    def _build_markers_param(
        self,
        markers: List[Tuple[float, float, str, str]],
    ) -> str:
        """
        构建 markers URL参数片段

        Args:
            markers: [(lng, lat, label, color), ...]
                label: 单字符或数字如 'A','B','1'
                color: 'red','blue','green','yellow','orange','purple','gray','black'

        Returns:
            markers URL参数字符串，如 "mid,0xFF0000,A:113.93,22.54;B:113.94,22.55"
        """
        if not markers:
            return ''

        parts = []
        for lng, lat, label, color in markers:
            c = self._format_color(color)
            parts.append(f"{c},{label}:{lng:.6f},{lat:.6f}")

        return '|'.join(parts)

    def _build_paths_param(
        self,
        paths: List[Tuple[List[Tuple[float, float]], str]],
    ) -> str:
        """
        构建 paths URL参数片段

        Args:
            paths: [([(lng, lat), ...], color), ...]
                每个元素: (坐标列表, 颜色)

        Returns:
            paths URL参数字符串，如 "5,0x0000FF,1,,:116.3,39.9;116.4,39.95"
        """
        if not paths:
            return ''

        parts = []
        for coords, color in paths:
            c = self._format_color(color)
            coord_str = ';'.join(f"{lng:.6f},{lat:.6f}" for lng, lat in coords)
            parts.append(f"5,{c},1,,:{coord_str}")

        return '|'.join(parts)

    def _build_labels_param(
        self,
        labels: List[Tuple[str, float, float, str, str]],
    ) -> str:
        """
        构建 labels URL参数片段

        Args:
            labels: [(content, lng, lat, fontColor, bgColor), ...]
                content: 标签文字（≤15字符）
                fontColor/bgColor: 'red','blue'等或'0xRRGGBB'

        Returns:
            labels URL参数字符串
        """
        if not labels:
            return ''

        parts = []
        for content, lng, lat, font_color, bg_color in labels:
            fc = self._format_color(font_color)
            bc = self._format_color(bg_color)
            parts.append(f"{content},2,0,12,{fc},{bc}:{lng:.6f},{lat:.6f}")

        return '|'.join(parts)

    def get_image(
        self,
        lng: float,
        lat: float,
        zoom: int = 15,
        width: int = 600,
        height: int = 400,
        scale: int = 1,
        markers: List[Tuple[float, float, str, str]] = None,
        paths: List[Tuple[List[Tuple[float, float]], str]] = None,
        labels: List[Tuple[str, float, float, str, str]] = None,
        traffic: int = 0,
        output_dir: Path = None,
        output_filename: str = None,
    ) -> Tuple[Optional[Path], Optional[dict]]:
        """
        获取一张高德静态地图（断点续传：已存在则跳过，不覆盖）

        Args:
            lng, lat:   地图中心点坐标 (WGS84)
            zoom:       缩放级别 [1,17]，默认15
            width:      图片宽度，最大1024，默认600
            height:     图片高度，最大1024，默认400
            scale:      1=普通图；2=高清图(尺寸翻倍,zoom+1)，默认1
            markers:    [(lng, lat, label, color), ...] 标注列表
            paths:      [([(lng, lat), ...], color), ...] 折线/多边形列表
            labels:     [(content, lng, lat, fontColor, bgColor), ...] 标签列表
            traffic:    0=无路况，1=显示实时路况，默认0
            output_dir: 保存目录，默认 IMAGES_DIR / 'amap_staticmap'
            output_filename: 自定义文件名（不含扩展名），默认按参数hash生成

        Returns:
            (文件路径, 元数据dict) 或 (None, None)
        """
        import requests

        if output_dir is None:
            output_dir = IMAGES_DIR / 'amap_staticmap'
        output_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名（按请求参数hash，确保不同参数生成不同文件）
        if output_filename is None:
            param_str = f"{lng:.6f}{lat:.6f}{zoom}{width}x{height}{scale}{traffic}"
            if markers:
                m_str = ';'.join(f"{m[0]:.4f},{m[1]:.4f},{m[2]},{m[3]}" for m in markers)
                param_str += m_str
            if paths:
                p_str = ';'.join(';'.join(f"{c[0]:.4f},{c[1]:.4f}" for c in p[0]) for p in paths)
                param_str += p_str
            file_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]
            filename = f"amap_sm_{file_hash}.png"
        else:
            filename = output_filename + '.png'

        filepath = output_dir / filename

        if filepath.exists():
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat, 'zoom': zoom}

        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)

        params: Dict[str, Any] = {
            'key': self._next_key(),
            'location': f"{gcj_lng:.6f},{gcj_lat:.6f}",
            'zoom': zoom,
            'size': f"{min(width, 1024)}*{min(height, 1024)}",
            'scale': scale,
            'traffic': traffic,
        }

        if markers:
            m_param = self._build_markers_param(markers)
            if m_param:
                params['markers'] = m_param

        if paths:
            p_param = self._build_paths_param(paths)
            if p_param:
                params['paths'] = p_param

        if labels:
            l_param = self._build_labels_param(labels)
            if l_param:
                params['labels'] = l_param

        try:
            resp = requests.get(self.BASE_URL, params=params, timeout=15)
            if resp.status_code == 200:
                ct = resp.headers.get('Content-Type', '')
                content = resp.content

                is_image = (
                    'image' in ct or
                    content[:3] == b'\xff\xd8\xff' or
                    b'PNG' in content[:10] or
                    b'JFIF' in content[:20]
                )

                if is_image and len(content) > 1000:
                    with open(filepath, 'wb') as f:
                        f.write(content)

                    return filepath, {
                        'status': 'success',
                        'size': len(content),
                        'lng': lng, 'lat': lat,
                        'gcj_lng': gcj_lng, 'gcj_lat': gcj_lat,
                        'zoom': zoom,
                        'width': width * scale,
                        'height': height * scale,
                        'scale': scale,
                        'markers': markers,
                        'paths': paths,
                        'source': 'amap_staticmap',
                    }

                try:
                    err_data = json.loads(content)
                    info = err_data.get('info', err_data.get('error', str(err_data)))
                    print(f"  [高德静态地图] ({lng:.4f},{lat:.4f}): {info}")
                    return None, {'status': 'error', 'info': info, 'lng': lng, 'lat': lat}
                except Exception:
                    pass

        except Exception as e:
            print(f"  [高德静态地图错误] ({lng:.4f},{lat:.4f}): {e}")

        return None, {'status': 'failed', 'lng': lng, 'lat': lat}

    def batch_collect(
        self,
        sample_df: pd.DataFrame,
        output_dir: Path = None,
        zoom: int = 15,
        width: int = 600,
        height: int = 400,
        scale: int = 1,
        delay: float = 2.0,
        checkpoint_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        批量采集高德静态地图（断点续传）

        Args:
            sample_df:     采样点DataFrame，需含 lng/lat 列
            output_dir:   保存目录，默认 IMAGES_DIR / 'amap_staticmap'
            zoom:         缩放级别，默认15
            width:        图片宽度，默认600
            height:       图片高度，默认400
            scale:        1=普通图，2=高清图，默认1
            delay:        请求间隔(秒)，默认2.0（避免触发QPS限制）
            checkpoint_path: 断点续传文件路径

        Returns:
            采集结果DataFrame
        """
        if output_dir is None:
            output_dir = IMAGES_DIR / 'amap_staticmap'

        results = []
        checkpoint: Dict[str, Any] = {}
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)

        total = len(sample_df)
        done, failed = 0, 0

        for _, row in sample_df.iterrows():
            lng = float(row['lng'])
            lat = float(row['lat'])

            param_str = f"{lng:.6f}{lat:.6f}{zoom}{width}x{height}{scale}"
            key_str = hashlib.md5(param_str.encode()).hexdigest()[:12]

            if key_str in checkpoint:
                done += 1
                continue

            filepath, meta = self.get_image(
                lng=lng, lat=lat,
                zoom=zoom, width=width, height=height, scale=scale,
                output_dir=output_dir,
            )
            results.append(meta or {'status': 'error', 'lng': lng, 'lat': lat})

            if meta and meta.get('status') == 'success':
                checkpoint[key_str] = meta
            else:
                failed += 1

            done += 1
            if done % 10 == 0:
                pct = 100 * done / total
                print(f"\r[高德静态地图] {done}/{total} ({pct:.0f}%) 失败≈{failed}", end='', flush=True)

            time.sleep(delay)

            if checkpoint_path and done % 50 == 0:
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint, f, ensure_ascii=False, indent=2)

        print()
        df_result = pd.DataFrame(results)
        if len(df_result) > 0 and output_dir:
            out = output_dir / 'amap_staticmap_metadata.csv'
            df_result.to_csv(out, index=False, encoding='utf-8-sig')
        return df_result

    def batch_collect_with_routes(
        self,
        sample_df: pd.DataFrame,
        routes_data: Dict[str, List[Tuple[float, float]]],
        output_dir: Path = None,
        zoom: int = 15,
        width: int = 600,
        height: int = 400,
        scale: int = 1,
        delay: float = 2.0,
        checkpoint_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        批量采集高德静态地图，同时在每张图上绘制步行路径（15分钟等时圈）

        Args:
            sample_df:   采样点DataFrame，需含 lng/lat 列
            routes_data: {(lng,lat)元组字符串: [(lng,lat), ...], ...}
                         每个采样点的路径/多边形坐标列表
            output_dir:  保存目录
            zoom/width/height/scale/delay/checkpoint_path: 同 batch_collect

        Returns:
            采集结果DataFrame
        """
        if output_dir is None:
            output_dir = IMAGES_DIR / 'amap_staticmap'

        results = []
        checkpoint: Dict[str, Any] = {}
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)

        total = len(sample_df)
        done, failed = 0, 0

        for _, row in sample_df.iterrows():
            lng = float(row['lng'])
            lat = float(row['lat'])

            coord_key = f"{lng:.6f},{lat:.6f}"
            route_coords = routes_data.get(coord_key, [])

            if route_coords:
                paths = [(route_coords, 'blue')]
                markers = [(lng, lat, 'A', 'red')]
            else:
                paths = []
                markers = []

            param_str = f"{lng:.6f}{lat:.6f}{zoom}{width}x{height}{scale}{coord_key}"
            key_str = hashlib.md5(param_str.encode()).hexdigest()[:12]

            if key_str in checkpoint:
                done += 1
                continue

            filepath, meta = self.get_image(
                lng=lng, lat=lat,
                zoom=zoom, width=width, height=height, scale=scale,
                markers=markers if markers else None,
                paths=paths if paths else None,
                output_dir=output_dir,
            )
            results.append(meta or {'status': 'error', 'lng': lng, 'lat': lat})

            if meta and meta.get('status') == 'success':
                checkpoint[key_str] = meta
            else:
                failed += 1

            done += 1
            if done % 10 == 0:
                pct = 100 * done / total
                print(f"\r[高德静态地图+路径] {done}/{total} ({pct:.0f}%) 失败≈{failed}", end='', flush=True)

            time.sleep(delay)

            if checkpoint_path and done % 50 == 0:
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint, f, ensure_ascii=False, indent=2)

        print()
        df_result = pd.DataFrame(results)
        if len(df_result) > 0 and output_dir:
            out = output_dir / 'amap_staticmap_routes_metadata.csv'
            df_result.to_csv(out, index=False, encoding='utf-8-sig')
        return df_result

    def get_usage(self) -> Dict[str, int]:
        """返回当前已使用的调用量"""
        return dict(self._usage)

    def get_remaining(self) -> int:
        """返回当前Key剩余可用次数"""
        k = self.keys[self._key_idx % len(self.keys)]
        return max(0, 500 - self._usage.get(k, 0))


# ============================================================================
# 高德API — 街景影像采集
# ============================================================================
# 高德街景API说明:
#   - 缩略图(Thumbnail): https://restapi.amap.com/v3/streetview/thumbnail
#     返回: 固定480x270缩略图，适合预览
#   - 街景数据(提供POI查询街景覆盖): https://restapi.amap.com/v3/streetview/getpois
#   - 完整街景需单独申请权限
#
# 计费: 需商务询价（不包含在普通Web服务配额内）

class AMapStreetViewAPI:
    """
    高德地图街景影像采集

    API说明:
      高德街景有多种接口:
      1. /v3/streetview/thumbnail — 缩略图(480x270)，需申请权限
      2. /v3/streetview/getpois — 查询指定坐标附近是否有街景
      3. 完整高清街景 — 需商务申请，单独计费

    注意:
      高德街景覆盖范围不如腾讯街景广，建议与腾讯API配合使用
      腾讯街景覆盖: https://lbs.qq.com/web/developer/govern-developer-resources/streetview

    申请方式:
      1. 控制台申请街景服务权限
      2. 工单说明用途（学术研究可申请免费测试额度）
    """

    def __init__(self, key: Union[str, List[str]]):
        if isinstance(key, str):
            self.key = key
        else:
            self.key = key[0]

    def check_streetview_available(
        self,
        lng: float,
        lat: float,
    ) -> Optional[dict]:
        """
        查询指定坐标是否有可用的街景数据。

        Args:
            lng, lat: WGS84坐标

        Returns:
            {
                'has_streetview': True/False,
                'location': (lng, lat),
                'pois': [{'id', 'name', 'location'}, ...]
            }
            None = 查询失败
        """
        import requests
        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)

        url = "https://restapi.amap.com/v3/streetview/getpois"
        params = {'key': self.key, 'location': f"{gcj_lng},{gcj_lat}"}

        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if data.get('status') == '1':
                pois = data.get('pois', [])
                return {
                    'has_streetview': len(pois) > 0,
                    'pois': pois,
                }
        except Exception as e:
            print(f"  [高德街景查询错误] ({lng:.4f},{lat:.4f}): {e}")

        return None

    def get_thumbnail(
        self,
        lng: float,
        lat: float,
        heading: float = 0,
        pitch: float = 0,
        output_dir: Path = None,
    ) -> Tuple[Optional[Path], Optional[dict]]:
        """
        获取高德街景缩略图（断点续传：已存在则跳过，不覆盖）

        Args:
            lng, lat: 坐标 (WGS84)
            heading: 水平方向角 (0-360)，0=北，90=东
            pitch: 俯仰角 (-90~90)，0=水平
            output_dir: 保存目录

        Returns:
            (文件路径, 元数据dict) 或 (None, None)
        """
        import requests

        if output_dir is None:
            output_dir = IMAGES_DIR / 'amap_thumbnail'
        output_dir.mkdir(parents=True, exist_ok=True)

        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:12]
        filename = f"amap_sv_{coord_hash}_h{int(heading)}.jpg"
        filepath = output_dir / filename

        # 断点续传核心：文件已存在则跳过，不重复下载
        if filepath.exists():
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat}

        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)

        url = "https://restapi.amap.com/v3/streetview/thumbnail"
        params = {
            'key': self.key,
            'location': f"{gcj_lng},{gcj_lat}",
            'heading': heading,
            'pitch': pitch,
            'scale': 1,
            'width': 480,
            'height': 270,
        }

        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                ct = resp.headers.get('Content-Type', '')
                if 'image' in ct or resp.content[:3] == b'\xff\xd8\xff':
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    return filepath, {
                        'status': 'success',
                        'size': len(resp.content),
                        'lng': lng, 'lat': lat,
                        'heading': heading, 'source': 'amap',
                    }
                elif 'json' in ct or 'text' in ct:
                    try:
                        err_data = resp.json()
                        if err_data.get('status') == '0':
                            return None, {'status': 'no_data', 'info': err_data.get('info')}
                    except Exception:
                        pass
        except Exception as e:
            print(f"  [高德街景错误] ({lng:.4f},{lat:.4f}): {e}")

        return None, {'status': 'failed', 'lng': lng, 'lat': lat}

    def batch_collect(
        self,
        sample_df: pd.DataFrame,
        output_dir: Path,
        headings: List[int] = None,
        delay: float = 0.3,
        checkpoint_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        批量采集高德街景缩略图（断点续传）

        Args:
            sample_df: 采样点DataFrame
            output_dir: 保存目录
            headings: 方向列表，默认 [0, 90, 180, 270]
            delay: 请求间隔(秒)
            checkpoint_path: 断点续传文件路径（JSON格式，已采集key列表）

        Returns:
            采集结果DataFrame
        """
        if headings is None:
            headings = [0, 90, 180, 270]

        results = []
        checkpoint = set()
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = set(json.load(f))

        total = len(sample_df) * len(headings)
        done, failed = 0, 0

        for _, row in sample_df.iterrows():
            lng, lat = float(row['lng']), float(row['lat'])
            point_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}".encode()).hexdigest()[:12]

            for heading in headings:
                key_str = f"{point_hash}_{int(heading)}"
                if key_str in checkpoint:
                    done += 1
                    continue

                filepath, meta = self.get_thumbnail(
                    lng, lat, heading,
                    output_dir=output_dir,
                )
                results.append(meta or {'status': 'error', 'lng': lng, 'lat': lat})

                if meta and meta.get('status') == 'success':
                    checkpoint.add(key_str)
                else:
                    failed += 1

                done += 1
                if done % 50 == 0:
                    print(f"\r[高德街景] {done}/{total} ({100 * done / total:.0f}%) 失败≈{failed}", end='', flush=True)

                time.sleep(delay)

            # 定期保存断点
            if checkpoint_path and len(checkpoint) % 100 == 0:
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(list(checkpoint), f)

        print()
        df_result = pd.DataFrame(results)
        if len(df_result) > 0:
            out = output_dir / 'amap_streetview_metadata.csv'
            df_result.to_csv(out, index=False, encoding='utf-8-sig')
        return df_result


# ============================================================================
# 腾讯API — 街景影像采集
# ============================================================================
# 腾讯街景覆盖: 深圳主城区覆盖较好，适合本项目
# API文档: https://lbs.qq.com/web/developer/govern-developer-resources/streetview
# 申请: 腾讯位置服务控制台 -> 服务管理 -> 街景

class TencentStreetViewAPI:
    """
    腾讯地图街景影像采集

    说明:
      - 腾讯街景是当前最可靠的深圳街景数据源
      - 坐标顺序注意: API参数是 lat,lng（纬度在前！与高德相反）
      - 需要申请「街景」服务权限（控制台服务管理）

    申请步骤:
      1. https://lbs.qq.com/ 注册/登录
      2. 控制台 -> 服务管理 -> 申请街景服务
      3. 获取 Key (WebService API Key)
    """

    def __init__(self, key: str):
        self.key = key

    def get_image(
        self,
        lng: float,
        lat: float,
        heading: float = 0,
        pitch: float = 0,
        output_dir: Path = None,
    ) -> Tuple[Optional[Path], Optional[dict]]:
        """
        获取一张腾讯街景影像（断点续传：已存在则跳过，不覆盖）

        注意: 腾讯API坐标顺序是 lat,lng（纬度在前！）

        Args:
            lng, lat: WGS84坐标
            heading: 方向角 (0-360)
            pitch: 俯仰角 (-90~90)
        """
        import requests

        if output_dir is None:
            output_dir = IMAGES_DIR / 'tencent'
        output_dir.mkdir(parents=True, exist_ok=True)

        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:12]
        filename = f"tencent_sv_{coord_hash}_h{int(heading)}.jpg"
        filepath = output_dir / filename

        # 断点续传核心：文件已存在则跳过，不重复下载
        if filepath.exists():
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat}

        # 腾讯坐标顺序: lat,lng（与高德相反！）
        url = (
            f"https://apis.map.qq.com/imagery/streetview/image"
            f"?location={lat},{lng}"
            f"&heading={heading}"
            f"&pitch={pitch}"
            f"&key={self.key}"
        )

        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200 and len(resp.content) > 5000:
                if resp.content[:3] == b'\xff\xd8\xff' or b'JFIF' in resp.content[:20]:
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    return filepath, {
                        'status': 'success',
                        'size': len(resp.content),
                        'lng': lng, 'lat': lat,
                        'heading': heading, 'source': 'tencent',
                    }
        except Exception as e:
            print(f"  [腾讯街景错误] ({lng:.4f},{lat:.4f}): {e}")

        return None, {'status': 'failed', 'lng': lng, 'lat': lat}

    def batch_collect(
        self,
        sample_df: pd.DataFrame,
        output_dir: Path,
        headings: List[int] = None,
        delay: float = 0.2,
        checkpoint_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """批量采集腾讯街景（断点续传）"""
        if headings is None:
            headings = [0, 90, 180, 270]

        results = []
        checkpoint = set()
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = set(json.load(f))

        total = len(sample_df) * len(headings)
        done, failed = 0, 0

        for _, row in sample_df.iterrows():
            lng, lat = float(row['lng']), float(row['lat'])
            point_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}".encode()).hexdigest()[:12]

            for heading in headings:
                key_str = f"{point_hash}_{int(heading)}"
                if key_str in checkpoint:
                    done += 1
                    continue

                filepath, meta = self.get_image(
                    lng, lat, heading,
                    output_dir=output_dir,
                )
                results.append(meta or {'status': 'error', 'lng': lng, 'lat': lat})

                if meta and meta.get('status') == 'success':
                    checkpoint.add(key_str)
                else:
                    failed += 1

                done += 1
                if done % 50 == 0:
                    print(f"\r[腾讯街景] {done}/{total} ({100 * done / total:.0f}%) 失败≈{failed}", end='', flush=True)

                time.sleep(delay)

            if checkpoint_path and len(checkpoint) % 100 == 0:
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(list(checkpoint), f)

        print()
        df_result = pd.DataFrame(results)
        if len(df_result) > 0:
            out = output_dir / 'tencent_streetview_metadata.csv'
            df_result.to_csv(out, index=False, encoding='utf-8-sig')
        return df_result


# ============================================================================
# 百度API — 全景静态图采集
# ============================================================================
# 百度全景静态图API v2（官方免费，无需申请街景专项权限）
# API文档: https://lbsyun.baidu.com/index.php?title=panonamasdk/statics
# 申请: https://lbsyun.baidu.com/ 注册 -> 控制台 -> 应用管理 -> 创建应用（for server）
#
# 特点:
#   ✅ 官方免费，申请简单（普通Web服务Key即可）
#   ✅ 支持WGS84坐标（coordtype=wgs84ll）
#   ✅ 可调分辨率（width:10-1024, height:10-512）
#   ✅ 直接返回图片，无需拼图
#   ✅ 水平视野可调（fov:10-360）
#
# 注意:
#   - 返回的是等距圆柱投影（Equirectangular）全景图
#   - heading=0为正北，顺时针增加
#   - 百度坐标使用BD-09，如使用WGS84需设置coordtype=wgs84ll

class BaiduStreetViewAPI:
    """
    百度全景静态图API v2 街景影像采集

    API说明:
      官方接口: https://api.map.baidu.com/panorama/v2
      无需申请街景专项权限，普通服务端AK即可使用
      直接返回图片，无需拼图

    申请步骤:
      1. https://lbsyun.baidu.com/ 注册/登录
      2. 控制台 -> 应用管理 -> 创建应用
      3. 类型选择「for server」（服务端专用）
      4. 复制AK即可使用

    优势对比:
      - 高德街景: 需单独申请权限，覆盖有限
      - 腾讯街景: 需申请街景服务权限
      - 百度全景: 普通AK即可，接口稳定，深圳覆盖好
    """

    def __init__(self, ak: str):
        self.ak = ak
        self.base_url = "https://api.map.baidu.com/panorama/v2"

    def get_image(
        self,
        lng: float,
        lat: float,
        heading: float = 0,
        pitch: float = 0,
        fov: float = 90,
        width: int = 512,
        height: int = 512,
        coordtype: str = 'wgs84ll',
        output_dir: Path = None,
    ) -> Tuple[Optional[Path], Optional[dict]]:
        """
        获取一张百度街景影像（断点续传：已存在则跳过，不覆盖）

        Args:
            lng, lat: WGS84坐标（coordtype=wgs84ll时）
            heading: 水平方向角 (0-360)，0=北，90=东，180=南，270=西
            pitch: 俯仰角 (0-90)，0=地平线，90=正上方
            fov: 水平视野范围 (10-360)，默认90
            width: 图片宽度 (10-1024)，默认512
            height: 图片高度 (10-512)，默认512
            coordtype: 坐标系，支持 wgs84ll / gcj02 / bd09ll
            output_dir: 保存目录

        Returns:
            (文件路径, 元数据dict) 或 (None, None)
        """
        import requests

        if output_dir is None:
            output_dir = IMAGES_DIR / 'baidu'
        output_dir.mkdir(parents=True, exist_ok=True)

        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:12]
        filename = f"baidu_sv_{coord_hash}_h{int(heading)}.jpg"
        filepath = output_dir / filename

        if filepath.exists():
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat}

        params = {
            'ak': self.ak,
            'location': f"{lng},{lat}",
            'heading': heading,
            'pitch': pitch,
            'fov': fov,
            'width': width,
            'height': height,
            'coordtype': coordtype,
        }

        try:
            resp = requests.get(self.base_url, params=params, timeout=15)
            if resp.status_code == 200:
                ct = resp.headers.get('Content-Type', '')
                content = resp.content

                if len(content) > 5000 and (
                    content[:3] == b'\xff\xd8\xff' or
                    b'JFIF' in content[:20] or
                    b'PNG' in content[:10]
                ):
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    return filepath, {
                        'status': 'success',
                        'size': len(content),
                        'lng': lng,
                        'lat': lat,
                        'heading': heading,
                        'pitch': pitch,
                        'fov': fov,
                        'width': width,
                        'height': height,
                        'coordtype': coordtype,
                        'source': 'baidu',
                    }

                if len(content) < 5000:
                    try:
                        err_data = json.loads(content)
                        err_msg = err_data.get('message', '') or err_data.get('msg', '')
                        if err_data.get('status') in (200, 400, 401):
                            return None, {
                                'status': 'no_data',
                                'info': err_msg,
                                'lng': lng,
                                'lat': lat,
                            }
                    except Exception:
                        pass

        except Exception as e:
            print(f"  [百度街景错误] ({lng:.4f},{lat:.4f}): {e}")

        return None, {'status': 'failed', 'lng': lng, 'lat': lat}

    def batch_collect(
        self,
        sample_df: pd.DataFrame,
        output_dir: Path,
        headings: List[int] = None,
        delay: float = 0.2,
        fov: float = 90,
        width: int = 512,
        height: int = 512,
        coordtype: str = 'wgs84ll',
        checkpoint_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        批量采集百度全景影像（断点续传）

        Args:
            sample_df: 采样点DataFrame
            output_dir: 保存目录
            headings: 方向列表，默认 [0, 90, 180, 270]
            delay: 请求间隔(秒)
            fov: 水平视野范围 (10-360)
            width: 图片宽度 (10-1024)
            height: 图片高度 (10-512)
            coordtype: 坐标系
            checkpoint_path: 断点续传文件路径

        Returns:
            采集结果DataFrame
        """
        if headings is None:
            headings = [0, 90, 180, 270]

        results = []
        checkpoint = set()
        if checkpoint_path and checkpoint_path.exists():
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = set(json.load(f))

        total = len(sample_df) * len(headings)
        done, failed = 0, 0

        for _, row in sample_df.iterrows():
            lng, lat = float(row['lng']), float(row['lat'])
            point_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}".encode()).hexdigest()[:12]

            for heading in headings:
                key_str = f"{point_hash}_{int(heading)}"
                if key_str in checkpoint:
                    done += 1
                    continue

                filepath, meta = self.get_image(
                    lng, lat,
                    heading=heading,
                    pitch=0,
                    fov=fov,
                    width=width,
                    height=height,
                    coordtype=coordtype,
                    output_dir=output_dir,
                )
                results.append(meta or {'status': 'error', 'lng': lng, 'lat': lat})

                if meta and meta.get('status') == 'success':
                    checkpoint.add(key_str)
                else:
                    failed += 1

                done += 1
                if done % 50 == 0:
                    print(f"\r[百度街景] {done}/{total} ({100 * done / total:.0f}%) 失败≈{failed}", end='', flush=True)

                time.sleep(delay)

            if checkpoint_path and len(checkpoint) % 100 == 0:
                with open(checkpoint_path, 'w', encoding='utf-8') as f:
                    json.dump(list(checkpoint), f)

        print()
        df_result = pd.DataFrame(results)
        if len(df_result) > 0:
            out = output_dir / 'baidu_streetview_metadata.csv'
            df_result.to_csv(out, index=False, encoding='utf-8-sig')
        return df_result


# ============================================================================
# 模拟采集模式
# ============================================================================

def simulate_collection(
    sample_df: pd.DataFrame,
    output_dir: Path,
    seed: int = 42,
) -> pd.DataFrame:
    """
    模拟采集模式 — 基于城市形态生成合成步行环境指标

    背景: 在正式采集之前，此模式可快速生成"伪数据"用于:
      - 验证分层采样的代表性
      - 测试后端分析流程
      - 论文方法论部分的基线对比

    指标说明:
      SCR (Street Coverage Ratio): 街道覆盖率
        = 采样点看到建筑外墙的视角比例
        城中村: SCR低（建筑密集、通道狭窄）
        高端社区: SCR高（街道宽阔、绿化丰富）

      BFD (Building Frontage Density): 建筑沿街密度
        = 沿街建筑立面长度 / 街道总长
        反映街道的"利用率"

      EWW (Effective Walkable Width): 有效步行宽度(米)
        = 可供步行的有效通道宽度
        城中村: EWW低（<1.5m）
        高端社区: EWW高（>3.0m）

      SVI (Street View Index): 街景综合指数
        = 0.5*SCR + 0.3*BFD + 0.2*(EWW归一化)
        综合反映街道步行环境质量
    """
    print(f"\n[模拟] 为 {len(sample_df)} 个采样点生成合成指标...")

    # 各形态的典型参数分布 (均值, 标准差)
    form_params: Dict[str, Dict[str, Tuple[float, float]]] = {
        'Village':         {'scr': (0.32, 0.10), 'bfd': (0.12, 0.06), 'eww': (1.4, 0.3)},
        'Village Fringe':   {'scr': (0.42, 0.10), 'bfd': (0.22, 0.08), 'eww': (1.9, 0.4)},
        'High-End':         {'scr': (0.72, 0.10), 'bfd': (0.58, 0.10), 'eww': (3.6, 0.5)},
        'High-Rise':        {'scr': (0.52, 0.08), 'bfd': (0.40, 0.08), 'eww': (2.6, 0.4)},
        'Mid-Rise':         {'scr': (0.60, 0.08), 'bfd': (0.34, 0.08), 'eww': (2.9, 0.4)},
        'Low-Rise':         {'scr': (0.72, 0.08), 'bfd': (0.50, 0.10), 'eww': (3.5, 0.5)},
        'Open/Other':       {'scr': (0.65, 0.12), 'bfd': (0.40, 0.12), 'eww': (3.0, 0.6)},
    }

    rng = np.random.default_rng(seed)
    records = []

    for _, row in sample_df.iterrows():
        form = row.get('urban_form', 'Open/Other')
        p = form_params.get(form, form_params['Open/Other'])

        scr = rng.normal(p['scr'][0], p['scr'][1])
        bfd = rng.normal(p['bfd'][0], p['bfd'][1])
        eww = rng.normal(p['eww'][0], p['eww'][1])
        scr = float(np.clip(scr, 0.05, 0.98))
        bfd = float(np.clip(bfd, 0.02, 0.95))
        eww = float(np.clip(eww, 0.3, 5.5))
        eww_norm = (eww - 0.3) / (5.5 - 0.3)
        svi = float(np.clip(0.5 * scr + 0.3 * bfd + 0.2 * eww_norm, 0.05, 0.98))

        records.append({
            'lng':             row['lng'],
            'lat':             row['lat'],
            'urban_form':      form,
            'road_fclass':     row.get('road_fclass', ''),
            'road_name':       row.get('road_name', ''),
            'SCR':             round(scr, 3),
            'BFD':             round(bfd, 3),
            'EWW_m':           round(eww, 2),
            'SVI':             round(svi, 3),
            'bld_density_100m':    row.get('bld_density_100m', 0),
            'avg_floors_100m':     round(row.get('avg_floors_100m', 0), 1),
            'village_nearby_cnt':   row.get('village_nearby_cnt', 0),
            'highend_nearby_cnt':   row.get('highend_nearby_cnt', 0),
            'mode':            'simulated',
        })

    df_result = pd.DataFrame(records)
    out_path = output_dir / 'simulated_streetview_metrics.csv'
    df_result.to_csv(out_path, index=False, encoding='utf-8-sig')
    print(f"[模拟] 保存: {out_path}")

    # 按形态输出统计
    print(f"\n[模拟] 各形态SVI统计 (验证假说):")
    for form, cnt in df_result.groupby('urban_form').size().items():
        s = df_result[df_result['urban_form'] == form]
        print(f"  {form:16s}: n={cnt:4d}, SCR={s['SCR'].mean():.3f}, "
              f"EWW={s['EWW_m'].mean():.2f}m, SVI={s['SVI'].mean():.3f}")

    return df_result


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='深圳南山区街景影像与POI数据采集系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 模拟模式（无需API Key，验证采样逻辑）
  python integrated_streetview_collector.py --mode simulate --n-samples 200

  # POI密度分析（需要高德API Key）
  python integrated_streetview_collector.py --mode simulate --amap-key YOUR_KEY --n-samples 200

  # 百度全景采集（[推荐] 官方免费，无需街景专项权限）
  python integrated_streetview_collector.py --mode baidu --baidu-ak YOUR_AK --n-samples 200

  # 腾讯街景采集
  python integrated_streetview_collector.py --mode tencent --tencent-key YOUR_KEY --n-samples 200

  # 高德街景采集
  python integrated_streetview_collector.py --mode amap --amap-key YOUR_KEY --n-samples 200

  # 跳过POI密度分析（节省配额）
  python integrated_streetview_collector.py --mode simulate --skip-poi --n-samples 200

  # 高德静态地图采集（[推荐] 同一Key，经济高效，500次/日）
  python integrated_streetview_collector.py --mode staticmap --amap-key YOUR_KEY --n-samples 200

  # 高德静态地图 + 高清 + 带路径叠加（需先完成等时圈计算）
  python integrated_streetview_collector.py --mode staticmap --amap-key YOUR_KEY --n-samples 200 --staticmap-scale 2 --staticmap-with-routes

  # 高德静态地图（自定义尺寸和缩放）
  python integrated_streetview_collector.py --mode staticmap --amap-key YOUR_KEY --n-samples 200 --staticmap-zoom 16 --staticmap-width 800 --staticmap-height 600

  # 百度全景采集
  python integrated_streetview_collector.py --mode baidu --baidu-ak YOUR_AK --n-samples 200

  # 腾讯街景采集
  python integrated_streetview_collector.py --mode tencent --tencent-key YOUR_KEY --n-samples 200

  # 高德街景采集（需单独申请权限）
  python integrated_streetview_collector.py --mode amap --amap-key YOUR_KEY --n-samples 200

高德API Key申请: https://lbs.amap.com/
腾讯API Key申请: https://lbs.qq.com/
百度AK申请: https://lbsyun.baidu.com/（控制台 → 应用管理 → 创建应用 → for server）
        """
    )

    # 采集模式
    parser.add_argument('--mode', choices=['simulate', 'amap', 'tencent', 'baidu', 'staticmap'],
                        default='simulate',
                        help='采集模式: simulate=合成指标; amap=高德街景; tencent=腾讯街景; baidu=百度全景; staticmap=高德静态地图(推荐)')

    # 静态地图配置
    parser.add_argument('--staticmap-zoom', type=int, default=15,
                        help='静态地图缩放级别 [1,17]，默认15（街道级）')
    parser.add_argument('--staticmap-width', type=int, default=600,
                        help='静态地图图片宽度，最大1024，默认600')
    parser.add_argument('--staticmap-height', type=int, default=400,
                        help='静态地图图片高度，最大1024，默认400')
    parser.add_argument('--staticmap-scale', type=int, default=1, choices=[1, 2],
                        help='静态地图精度: 1=普通图; 2=高清图(尺寸翻倍,zoom+1)，默认1')
    parser.add_argument('--staticmap-delay', type=float, default=2.0,
                        help='静态地图请求间隔(秒)，默认2.0（避免QPS限制）')
    parser.add_argument('--staticmap-with-routes', action='store_true',
                        help='在静态地图上叠加步行路径（需先完成等时圈计算）')

    # API密钥
    parser.add_argument('--amap-key', default=None,
                        help='高德API Key（用于POI/街景/AOI/地理编码等所有高德服务）')
    parser.add_argument('--tencent-key', default=None,
                        help='腾讯API Key（用于腾讯街景采集）')
    parser.add_argument('--baidu-ak', default=None,
                        help='百度AK（用于百度全景静态图API，推荐免费方案）')

    # 采样配置
    parser.add_argument('--n-samples', type=int, default=None,
                        help='目标采样点数（None=全量路网采样）')
    parser.add_argument('--seed', type=int, default=42,
                        help='随机种子（保证结果可复现）')

    # 街景采集配置
    parser.add_argument('--headings', type=int, default=4,
                        help='每个点采集方向数 (1=单方向, 4=四方向)')
    parser.add_argument('--delay', type=float, default=0.2,
                        help='API请求间隔(秒)，默认0.2（QPS=5，低于限制）')
    parser.add_argument('--min-file-size', type=int, default=5000,
                        help='街景文件最小字节数（低于此值视为无效/空数据，默认5000）')
    parser.add_argument('--quality-filter', action='store_true',
                        help='对已采集影像进行质量过滤（删除模糊/过暗/无效影像）')

    # POI配置
    parser.add_argument('--poi-radii', default='100,300,500',
                        help='POI密度查询半径(米)，逗号分隔')
    parser.add_argument('--poi-types', default=None,
                        help='POI类型，逗号分隔（默认: transit/education/hospital/commerce/park）')
    parser.add_argument('--skip-poi', action='store_true',
                        help='跳过POI密度查询（节省API配额）')

    # 额外API配置
    parser.add_argument('--skip-regeo', action='store_true',
                        help='跳过逆地理编码（节省API配额）')
    parser.add_argument('--skip-weather', action='store_true',
                        help='跳过天气查询')
    parser.add_argument('--skip-isochrone', action='store_true',
                        help='跳过等时圈分析（步行路径规划）')
    parser.add_argument('--regeo-limit', type=int, default=20,
                        help='逆地理编码最大条数（默认20，设为0则全部编码）')
    parser.add_argument('--aoi-mode', action='store_true',
                        help='AOI边界采集模式：搜索城中村/小区名称并获取精确边界')

    args = parser.parse_args()

    # ── 环境变量兜底（方便批量使用 / 隐私保护）──────────────────────────
    if not args.baidu_ak:
        args.baidu_ak = os.environ.get('BAIDU_AK', '')
    if not args.tencent_key:
        args.tencent_key = os.environ.get('TENCENT_KEY', '')
    if not args.amap_key:
        args.amap_key = os.environ.get('AMAP_KEY', '')

    # ── 打印配置信息 ──
    print("=" * 68)
    print("深圳南山区街景影像与POI数据采集系统")
    print("Integrated Street View & POI Acquisition for Nanshan District, Shenzhen")
    print("=" * 68)
    print(f"  采集模式: {args.mode.upper()}")
    print(f"  目标采样: {args.n_samples or '无 (全量路网)'}")
    print(f"  POI半径:  {args.poi_radii} m  (跳过: {args.skip_poi})")
    print(f"  API延迟:  {args.delay}s")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  高德Key:  {'[OK]' if args.amap_key else '[--] 未配置 (使用模拟)'}")
    print(f"  腾讯Key:  {'[OK]' if args.tencent_key else '[--] 未配置'}")
    print(f"  百度AK:   {'[OK]' if args.baidu_ak else '[--] 未配置'}")
    print("=" * 68)

    # ── 创建目录结构 ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: 加载路网 ──
    print(f"\n[Step 1/8] 加载OSM路网...")
    shp_path = OSM_DIR / 'nanshan_road_network.shp'
    if not shp_path.exists():
        print(f"[错误] 路网文件不存在: {shp_path}")
        print("请先下载OSM数据: https://www.openstreetmap.org/export")
        return
    road_gdf = load_road_network(shp_path)

    # ── Step 2: 加载楼栋 ──
    print(f"\n[Step 2/8] 加载楼栋数据...")
    building_df = load_building_data()

    # ── Step 3: 沿路网均匀采样 ──
    print(f"\n[Step 3/8] 沿路网均匀采样...")
    sample_df = sample_along_roads(road_gdf, ROAD_SAMPLE_INTERVALS, seed=args.seed)

    # ── Step 4: 城市形态分层 ──
    print(f"\n[Step 4/8] 城市形态分类...")
    sample_df = classify_urban_form(sample_df, building_df)

    # ── Step 5: 分层降采样 ──
    print(f"\n[Step 5/8] 分层降采样...")
    if args.n_samples and len(sample_df) > args.n_samples:
        sample_df = stratified_downsample(
            sample_df,
            n_target=args.n_samples,
            building_df=building_df,
            seed=args.seed,
        )
    else:
        print(f"[降采样] 跳过 (当前 {len(sample_df)} 点 <= 目标无限制)")

    # ── Step 5b: AOI边界采集模式（独立运行）──────────────────────────
    if args.aoi_mode:
        if not args.amap_key:
            print("[错误] AOI模式需要 --amap-key")
            return
        print(f"\n[Step 5b/8] AOI边界采集模式...")
        aoi_cache_dir = META_DIR / 'aoi_cache'
        aoi_cache_dir.mkdir(parents=True, exist_ok=True)
        aoi_api = AMapAOIAPI(args.amap_key, cache_dir=aoi_cache_dir)
        poi_api = AMapPOIAPI(args.amap_key, cache_dir=aoi_cache_dir)

        # 南山区典型城中村/小区关键词列表
        village_keywords = [
            '村', '股份公司', '旧村', '新村', '围仔', '围', '厦', '塘朗村', '大冲村',
            '白石洲', '桂庙', '新塘村', '平山村', '大园村', '龙联村', '珠光村',
        ]
        all_aois = []
        for kw in village_keywords:
            print(f"[AOI] 搜索关键词: {kw}...")
            pois = poi_api.search_by_keyword(keyword=kw, city='深圳')
            print(f"  → 找到 {len(pois)} 个POI")
            for poi in pois:
                boundary = aoi_api.get_aoi_boundary(poi['poi_id'])
                all_aois.append({
                    **poi,
                    'boundary_wgs84': boundary,
                    'has_boundary': boundary is not None,
                    'search_keyword': kw,
                })
                time.sleep(args.delay)
            time.sleep(0.2)

        aoi_df = pd.DataFrame([{
            'poi_id': a.get('poi_id', ''),
            'poi_name': a.get('poi_name', ''),
            'poi_type': a.get('poi_type', ''),
            'lng_wgs84': a.get('lng_wgs84'),
            'lat_wgs84': a.get('lat_wgs84'),
            'address': a.get('address', ''),
            'has_boundary': a.get('has_boundary', False),
            'search_keyword': a.get('search_keyword', ''),
        } for a in all_aois])
        aoi_out = SAMPLES_DIR / 'aoi_boundaries.csv'
        aoi_df.to_csv(aoi_out, index=False, encoding='utf-8-sig')
        print(f"\n[AOI完成] 共 {len(aoi_df)} 个AOI，有边界 {aoi_df['has_boundary'].sum()} 个")
        print(f"  → 保存至: {aoi_out}")

        # 保存带坐标的GeoJSON（可用于ArcGIS/QGIS）
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon
            features = []
            for _, row in aoi_df[aoi_df['has_boundary']].iterrows():
                pts = row.get('boundary_wgs84')
                if pts and len(pts) >= 3:
                    features.append({
                        'type': 'Feature',
                        'geometry': {'type': 'Polygon', 'coordinates': [pts]},
                        'properties': {
                            'poi_id': row.get('poi_id', ''),
                            'poi_name': row.get('poi_name', ''),
                            'search_keyword': row.get('search_keyword', ''),
                        }
                    })
            if features:
                geojson = {'type': 'FeatureCollection', 'features': features}
                gj_out = META_DIR / 'aoi_boundaries.geojson'
                with open(gj_out, 'w', encoding='utf-8') as f:
                    json.dump(geojson, f, ensure_ascii=False)
                print(f"  → GeoJSON边界已保存: {gj_out}")
        except ImportError:
            print("[提示] 安装geopandas可导出GeoJSON: pip install geopandas")
        return  # AOI模式独立运行，完成后直接退出

    # ── Step 6: POI密度查询 ──
    if not args.skip_poi and args.amap_key:
        print(f"\n[Step 6/8] POI密度分析...")
        poi_radii = [int(r) for r in args.poi_radii.split(',')]
        poi_cache_dir = META_DIR / 'poi_cache'
        poi_cache_dir.mkdir(parents=True, exist_ok=True)
        poi_client = AMapPOIAPI(args.amap_key, cache_dir=poi_cache_dir)
        sample_df = poi_client.calculate_poi_density(
            sample_df,
            radii=poi_radii,
            delay=args.delay,
        )
    elif not args.skip_poi and not args.amap_key:
        print(f"\n[Step 6/8] POI密度分析 — 无高德Key，跳过")
        print(f"        申请地址: https://lbs.amap.com/ (免费5000次/日)")

    # ── Step 6b: 等时圈分析（全量采样点，15分钟步行可达范围）─────
    if args.amap_key and not args.skip_isochrone:
        print(f"\n[Step 6b/8] 等时圈分析 (15分钟步行可达范围)...")
        iso_cache_dir = META_DIR / 'isochrone_cache'
        iso_cache_dir.mkdir(parents=True, exist_ok=True)
        dir_api = AMapDirectionAPI(args.amap_key, cache_dir=iso_cache_dir)
        iso_records = []
        coords = list(zip(sample_df['lng'], sample_df['lat']))
        for i, (lng, lat) in enumerate(coords):
            iso = dir_api.walking_isochrone(lng, lat, time_minutes=15)
            if iso and isinstance(iso, dict):
                iso_records.append({
                    'lng': lng,
                    'lat': lat,
                    'iso_distance_m': iso.get('total_distance_m', 0),
                    'iso_duration_s': iso.get('total_duration_s', 0),
                    'iso_roads': iso.get('reachable_roads', 0),
                    'iso_area_km2': iso.get('area_km2_est', 0.0),
                })
            else:
                iso_records.append({
                    'lng': lng, 'lat': lat,
                    'iso_distance_m': 0, 'iso_duration_s': 0,
                    'iso_roads': 0, 'iso_area_km2': 0.0,
                })
            if (i + 1) % 20 == 0:
                print(f"  进度 {i + 1}/{len(coords)} ({100*(i+1)/len(coords):.0f}%)", end='', flush=True)
            time.sleep(args.delay)
        print()
        iso_df = pd.DataFrame(iso_records)
        for col in iso_df.columns:
            if col not in ('lng', 'lat'):
                sample_df[col] = iso_df[col].values
        # 保存等时圈边界（JSON）
        iso_out = META_DIR / 'isochrone_boundaries.json'
        with open(iso_out, 'w', encoding='utf-8') as f:
            json.dump({f"{r['lng']:.6f}_{r['lat']:.6f}": r for r in iso_records}, f, ensure_ascii=False)
        print(f"[等时圈] 已保存 {len(iso_records)} 条数据 → {iso_out}")

    # ── Step 7: 额外API（逆地理编码/天气）─────────────
    if args.amap_key and not args.skip_regeo:
        geo_cache_dir = META_DIR / 'geocoding_cache'
        geo_cache_dir.mkdir(parents=True, exist_ok=True)
        geo_api = AMapGeocodingAPI(args.amap_key, cache_dir=geo_cache_dir)
        print(f"\n[Step 7a/8] 逆地理编码...")
        addresses = []
        coords = list(zip(sample_df['lng'], sample_df['lat']))
        limit = args.regeo_limit if args.regeo_limit > 0 else len(coords)
        for lng, lat in coords[:min(limit, len(coords))]:
            addr = geo_api.regeocode(lng, lat)
            if addr:
                addresses.append(addr.get('formatted_address', ''))
            time.sleep(args.delay)
        print(f"[逆编码] 完成 {len(addresses)} 条")

    if args.amap_key and not args.skip_weather:
        print(f"\n[Step 7b/8] 天气数据...")
        weather_api = AMapWeatherAPI(args.amap_key, cache_dir=META_DIR / 'weather_cache')
        weather_cache_dir = META_DIR / 'weather_cache'
        weather_cache_dir.mkdir(parents=True, exist_ok=True)
        weather = weather_api.get_weather('440305', extensions='base')
        if weather:
            print(f"[天气] {weather.get('city','')} {weather.get('weather','')} "
                  f"{weather.get('temperature','')}°C")

    # ── 保存采样点 ──
    sample_out = SAMPLES_DIR / f'sample_points_n{len(sample_df)}.csv'
    sample_df.to_csv(sample_out, index=False, encoding='utf-8-sig')
    print(f"\n[保存] 采样点已保存: {sample_out}")

    # ── Step 8: 街景/模拟采集 ──
    headings = [0] if args.headings == 1 else [0, 90, 180, 270]
    total_images = len(sample_df) * len(headings)

    if args.mode == 'simulate':
        print(f"\n[Step 8/8] 模拟模式 — 生成合成指标...")
        simulate_collection(sample_df, OUTPUT_DIR, seed=args.seed)

    elif args.mode == 'amap':
        if not args.amap_key:
            print("[错误] 高德模式需要 --amap-key")
            return
        print(f"\n[Step 8/8] 高德街景采集 ({total_images} 张)...")
        client = AMapStreetViewAPI(args.amap_key)
        ckpt = META_DIR / '.amap_checkpoint.json'
        client.batch_collect(
            sample_df, IMAGES_DIR / 'amap',
            headings=headings, delay=args.delay,
            checkpoint_path=ckpt,
        )

    elif args.mode == 'tencent':
        if not args.tencent_key:
            print("[错误] 腾讯模式需要 --tencent-key")
            return
        print(f"\n[Step 8/8] 腾讯街景采集 ({total_images} 张)...")
        client = TencentStreetViewAPI(args.tencent_key)
        ckpt = META_DIR / '.tencent_checkpoint.json'
        client.batch_collect(
            sample_df, IMAGES_DIR / 'tencent',
            headings=headings, delay=args.delay,
            checkpoint_path=ckpt,
        )

    elif args.mode == 'baidu':
        if not args.baidu_ak:
            print("[错误] 百度模式需要 --baidu-ak")
            return
        print(f"\n[Step 8/8] 百度全景采集 ({total_images} 张)...")
        client = BaiduStreetViewAPI(args.baidu_ak)
        ckpt = META_DIR / '.baidu_checkpoint.json'
        client.batch_collect(
            sample_df, IMAGES_DIR / 'baidu',
            headings=headings, delay=args.delay,
            checkpoint_path=ckpt,
        )

    elif args.mode == 'staticmap':
        if not args.amap_key:
            print("[错误] 静态地图模式需要 --amap-key")
            return
        print(f"\n[Step 8/8] 高德静态地图采集 ({len(sample_df)} 张)...")
        print(f"  zoom={args.staticmap_zoom}  size={args.staticmap_width}x{args.staticmap_height}  "
              f"scale={args.staticmap_scale}  delay={args.staticmap_delay}s")
        api = AmapStaticMapAPI(args.amap_key)
        ckpt = META_DIR / '.amap_staticmap_checkpoint.json'

        if args.staticmap_with_routes:
            routes_cache = META_DIR / 'walking_routes.json'
            routes_data: Dict[str, Any] = {}
            if routes_cache.exists():
                with open(routes_cache, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                    for item in raw:
                        key = item.get('origin', '')
                        poly = item.get('polygon', [])
                        if key and poly:
                            routes_data[key] = [(p[0], p[1]) for p in poly]
            if not routes_data:
                print("[警告] 未找到等时圈路径数据，采集无路径叠加的静态地图")
            df_result = api.batch_collect_with_routes(
                sample_df, routes_data,
                output_dir=IMAGES_DIR / 'amap_staticmap',
                zoom=args.staticmap_zoom,
                width=args.staticmap_width,
                height=args.staticmap_height,
                scale=args.staticmap_scale,
                delay=args.staticmap_delay,
                checkpoint_path=ckpt,
            )
        else:
            df_result = api.batch_collect(
                sample_df,
                output_dir=IMAGES_DIR / 'amap_staticmap',
                zoom=args.staticmap_zoom,
                width=args.staticmap_width,
                height=args.staticmap_height,
                scale=args.staticmap_scale,
                delay=args.staticmap_delay,
                checkpoint_path=ckpt,
            )

        usage = api.get_usage()
        print(f"  高德静态地图配额: {dict(usage)}")

    # ── Step 8b: 影像质量过滤 ──
    if args.quality_filter:
        print(f"\n[Step 8b/8] 影像质量过滤...")
        img_filter = ImageQualityFilter(
            min_file_size=args.min_file_size,
            min_brightness=20.0,
            max_brightness=230.0,
            min_sharpness=50.0,
            min_valid_ratio=0.3,
        )
        # 依次过滤高德/腾讯影像目录
        for sv_dir in [IMAGES_DIR / 'amap', IMAGES_DIR / 'tencent', IMAGES_DIR / 'baidu']:
            if sv_dir.exists():
                r = img_filter.filter_directory(sv_dir)
                print(f"[质量过滤] {sv_dir.name}: 合格 {r['valid']}/{r['total']}, "
                      f"删除 {r['deleted']}, 合格率 {100*r['valid']/max(r['total'],1):.1f}%")
            else:
                print(f"[质量过滤] 目录不存在: {sv_dir}，跳过")

    # ── 完成报告 ──
    print("\n" + "=" * 68)
    print("采集完成 / Acquisition Complete")
    print(f"  采样点: {SAMPLES_DIR}")
    print(f"  影像目录: {IMAGES_DIR}")
    print(f"  元数据: {META_DIR}")
    print(f"  质量过滤: {'已启用' if args.quality_filter else '未启用'}")
    if args.amap_key:
        poi_client_summary = AmapBatchClient(args.amap_key)
        usage = poi_client_summary.get_usage_report()
        print(f"  高德配额使用: {dict(usage)}")
    print("=" * 68)


if __name__ == '__main__':
    main()


# =============================================================================
# =============================================================================
# =============================================================================
# 高德API配置详解 / Amap API Configuration Guide
# =============================================================================
# =============================================================================
# =============================================================================
#
# 一、API Key 申请步骤
# --------------------
#
# 1. 注册账号
#    访问 https://lbs.amap.com/ -> 免费注册
#
# 2. 创建应用
#    控制台 -> 我的应用 -> 创建应用
#    应用名称: "15分钟城市研究-南山街景"
#    类型: Web服务
#
# 3. 添加Key
#    应用详情 -> 添加Key
#    服务平台: Web服务(后续可添加Android/iOS)
#    Key名称: "research-key-1"
#    勾选"我已阅读并同意《高德地图开放平台协议》"
#    提交后获得 Key (32位字母数字)
#
# 4. 权限说明
#    Web服务Key默认开通:
#      - POI搜索 (place/text, place/around, place/polygon)
#      - 地理编码 (geocode/geocode, geocode/regeo)
#      - 行政区划 (config/district)
#      - 天气查询 (weather/weatherInfo)
#      - 路径规划 (direction/walking)
#      - 街景缩略图 (streetview/thumbnail) — 需额外申请
#      - AOI边界 (v5/aoi/polyline) — 需工单申请高阶权限
#
# 5. 权限申请（工单）
#    控制台 -> 工单系统 -> 新建工单
#    类别: 服务咨询 -> 权限开通
#    内容: "学术研究使用，需开通AOI边界查询和街景服务"
#    预计处理: 1-3个工作日
#
#
# 二、各API功能对照表
# ------------------
#
# ┌──────────────────────┬──────────────────────┬───────────┬──────────────┐
# │ API功能              │ 端点                   │ 计费       │ 配额/日免费   │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ POI关键字搜索        │ v3/place/text         │ ¥0.01/次  │ 10万次       │
# │ POI周边搜索          │ v3/place/around       │ ¥0.01/次  │ 10万次       │
# │ POI多边形搜索        │ v3/place/polygon       │ ¥0.01/次  │ 10万次       │
# │ POI ID详情           │ v3/place/detail        │ ¥0.01/次  │ 10万次       │
# │ AOI边界查询          │ v5/aoi/polyline        │ 单独计费   │ 需申请权限   │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ 地理编码             │ v3/geocode/geocode     │ ¥0.001/次 │ 500万次      │
# │ 逆地理编码           │ v3/geocode/regeo       │ ¥0.001/次 │ 500万次      │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ 行政区划查询         │ v3/config/district      │ ¥0.001/次 │ 500万次      │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ 天气预报             │ v3/weather/weatherInfo  │ ¥0.001/次 │ 500万次      │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ 步行路线规划         │ v3/direction/walking     │ ¥0.005/次 │ 100万次      │
# │ 公交路线规划         │ v3/direction/transit    │ ¥0.01/次  │ 50万次       │
# ├──────────────────────┼──────────────────────┼───────────┼──────────────┤
# │ 街景缩略图           │ v3/streetview/thumbnail │ 单独计费   │ 需申请权限   │
# │ 街景覆盖查询         │ v3/streetview/getpois   │ 单独计费   │ 需申请权限   │
# └──────────────────────┴──────────────────────┴───────────┴──────────────┘
#
# 注: 免费用户每个Key每日5000次基础调用，超出按上方计费标准
#     申请企业认证后可获得更高配额
#
#
# 三、本研究各API用途汇总
# ---------------------
#
# 【POI密度分析 — 15分钟城市核心指标】
#   使用API: v3/place/around
#   调用量: 采样点数 × 3个半径 × 5个类型 ≈ 200 × 3 × 5 = 3000次/天
#   配额消耗: 约3000 × ¥0.01 = ¥30/天 (或用免费额度)
#
# 【AOI边界获取 — 城中村/小区精确边界】
#   使用API: v5/aoi/polyline (高阶权限)
#   调用量: 城中村/小区数量 × 1次 ≈ 100-500次
#   替代方案: 用POI搜索的location字段作为中心点
#
# 【逆地理编码 — 采样点地址标注】
#   使用API: v3/geocode/regeo
#   调用量: 采样点数 × 1次 ≈ 200次/天
#   配额消耗: ¥0.001 × 200 = ¥0.2/天
#
# 【行政区划 — 自动获取研究区边界】
#   使用API: v3/config/district
#   调用量: 1次（获取南山区边界）
#   配额消耗: ¥0.001 × 1 ≈ ¥0.001/天
#
# 【天气数据 — 环境因素叠加】
#   使用API: v3/weather/weatherInfo
#   调用量: 1次/天（天气日变化不大）
#   配额消耗: ¥0.001 × 1 = ¥0.001/天
#
# 【步行等时圈 — 15分钟可达范围】
#   使用API: v3/direction/walking
#   调用量: 采样点数 × 1次 ≈ 200次/天
#   配额消耗: ¥0.005 × 200 = ¥1/天
#
# 【街景采集】
#   高德: v3/streetview/thumbnail (需申请权限)
#   腾讯: apis.map.qq.com (需申请街景服务权限)
#   调用量: 200点 × 4方向 = 800次
#
# 合计每日API成本估算（无免费额度时）:
#   POI(3000) + 逆编码(200) + 等时圈(200) + 街景(800)
#   ≈ ¥30 + ¥0.2 + ¥1 + ¥0 = ¥31.2/天
#
#
# 四、批量请求优化建议
# -------------------
#
# 1. 多Key轮询
#    申请3-5个Key，每个Key每日5000次，合计15000-25000次/天
#    本系统的 AmapBatchClient 已自动支持多Key轮询:
#    python integrated_streetview_collector.py --amap-key "key1,key2,key3" ...
#
# 2. 缓存策略
#    相同坐标+相同参数的请求结果缓存到本地
#    本系统的 AmapBatchClient.cached_get() 已自动实现
#    缓存目录: META_DIR/poi_cache, geocoding_cache, ...
#
# 3. 速率控制
#    高德服务端限制: 30 QPS
#    建议请求间隔: 0.1-0.2秒 (QPS=5-10，留有余量)
#    本系统的 MIN_DELAY = 1/30 ≈ 0.033秒 (理论最小)
#
# 4. 断点续传
#    网络中断后，从上次完成的点继续
#    本系统所有批量采集都支持 --checkpoint 参数
#
#
# 五、腾讯API配置
# --------------
#
# 1. 申请地址: https://lbs.qq.com/
# 2. 控制台 -> 服务管理 -> 街景服务 -> 申请权限
# 3. 获取 Key (WebService API Key)
# 4. 腾讯街景优势: 深圳主城区覆盖较好，无需额外权限申请
#
# =============================================================================
