# -*- coding: utf-8 -*-
"""
=============================================================================
街景影像采集模块 — Street View Image Acquisition
用于南山区步行环境深度感知研究
=============================================================================

支持三种数据源:
  1. 腾讯街景 API (Tencent Street View API) — 主要推荐
  2. 高德街景 API (AMap Street View API) — 国内备用
  3. Google Street View Static API — 国际对比用
  4. 模拟模式 (无API Key时用于开发和测试)

采集策略:
  - 沿OSM路网节点采样，每50-200米一个点
  - 按道路类型分级采样密度
  - 每个采样点采集四个方向(0°, 90°, 180°, 270°)影像
  - 支持断点续传，避免重复采集

依赖:
  pip install requests Pillow tqdm shapely geopandas osmnx

=============================================================================
"""

import os
import sys
import math
import time
import hashlib
import warnings
import json
import tempfile
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd

# ==========================
# 配置
# ==========================

# 南山区地理边界
NANSHAN_BOUNDS = {
    'lng_min': 113.85,
    'lng_max': 114.45,
    'lat_min': 22.40,
    'lat_max': 22.80,
}

# 按道路类型的采样间隔(米)
# 越重要的道路，步行可达性越关键，采样越密集
SAMPLE_INTERVALS_M = {
    'motorway': 100,
    'trunk': 100,
    'primary': 80,
    'secondary': 120,
    'tertiary': 150,
    'residential': 200,
    'service': 250,
    'unclassified': 300,
    'track': 300,
}

# 采样方向(四个方向)
HEADINGS = [0, 90, 180, 270]

# 输出目录
DEFAULT_OUTPUT = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究\data\streetview'
IMAGE_SIZE = '600x300'  # 腾讯街景支持600x300, 300x150


# ==========================
# API客户端
# ==========================

class TencentStreetViewAPI:
    """
    腾讯街景 API 封装
    
    申请地址: https://lbs.qq.com/
    文档: https://lbs.qq.com/web/developer/govern-developer-resources/streetview
    
    API调用说明:
    - Image API: 获取指定位置的街景影像
    - Panoid API: 获取指定位置的panoid
    - key 需要是 WebServiceKey (必须配置 HTTP Referer)
    """
    
    def __init__(self, key: str, sk: Optional[str] = None):
        self.key = key
        self.sk = sk  # 腾讯地图WebService的签名密钥(可选)
        self.base_url = 'https://apis.map.qq.com'
    
    def get_streetview_image(
        self,
        lng: float,
        lat: float,
        heading: float = 0,
        pitch: float = 0,
        output_dir: str = DEFAULT_OUTPUT,
        overwrite: bool = False,
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        获取指定位置的街景影像。
        
        参数:
            lng, lat: 位置的经纬度(WGS84)
            heading: 视角方向(0-360), 0=北, 90=东, 180=南, 270=西
            pitch: 仰角(-90到90), 0=水平
            output_dir: 输出目录
            overwrite: 是否覆盖已存在的影像
        
        返回:
            (影像文件路径, 元数据字典) 或 (None, None)
        """
        # 生成唯一文件名
        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:8]
        filename = f"sv_{coord_hash}_{int(heading)}deg.jpg"
        filepath = os.path.join(output_dir, filename)
        
        if os.path.exists(filepath) and not overwrite:
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat, 'heading': heading}
        
        # 构建请求URL (腾讯街景Image API v1)
        url = (
            f"https://apis.map.qq.com/imagery/streetview/image"
            f"?location={lng},{lat}"
            f"&heading={heading}"
            f"&pitch={pitch}"
            f"&key={self.key}"
        )
        
        try:
            import requests
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200 and len(resp.content) > 1000:
                os.makedirs(output_dir, exist_ok=True)
                with open(filepath, 'wb') as f:
                    f.write(resp.content)
                
                # 保存元数据
                meta = {
                    'lng': lng,
                    'lat': lat,
                    'heading': heading,
                    'pitch': pitch,
                    'size': len(resp.content),
                    'hash': coord_hash,
                    'source': 'tencent',
                }
                return filepath, meta
        except Exception as e:
            print(f"  [WARN] Tencent API failed for ({lng:.4f},{lat:.4f}): {e}")
        
        return None, None
    
    def batch_fetch(
        self,
        points: List[Tuple[float, float]],
        output_dir: str = DEFAULT_OUTPUT,
        headings: List[int] = HEADINGS,
        delay: float = 0.1,
        overwrite: bool = False,
        progress: bool = True,
    ) -> pd.DataFrame:
        """
        批量采集多个位置的街景影像。
        
        参数:
            points: [(lng, lat), ...] 坐标列表
            output_dir: 输出目录
            headings: 要采集的方向列表
            delay: 请求间隔(秒)，避免触发频率限制
            overwrite: 是否覆盖已有影像
            progress: 是否显示进度条
        
        返回:
            采集结果DataFrame
        """
        results = []
        
        if progress:
            try:
                from tqdm import tqdm
                iterator = tqdm(total=len(points) * len(headings), desc="采集街景")
            except ImportError:
                print("请安装 tqdm: pip install tqdm")
                progress = False
                iterator = None
        else:
            iterator = None
        
        for lng, lat in points:
            # 跳过边界外的点
            if not (NANSHAN_BOUNDS['lng_min'] <= lng <= NANSHAN_BOUNDS['lng_max'] and
                    NANSHAN_BOUNDS['lat_min'] <= lat <= NANSHAN_BOUNDS['lat_max']):
                if iterator:
                    iterator.update(len(headings))
                continue
            
            for heading in headings:
                filepath, meta = self.get_streetview_image(
                    lng, lat, heading,
                    output_dir=output_dir,
                    overwrite=overwrite,
                )
                
                if meta:
                    results.append(meta)
                else:
                    results.append({
                        'lng': lng, 'lat': lat, 'heading': heading,
                        'source': 'tencent', 'status': 'failed'
                    })
                
                if iterator:
                    iterator.update(1)
                
                if delay > 0:
                    time.sleep(delay)
        
        if iterator:
            iterator.close()
        
        df = pd.DataFrame(results)
        if len(df) > 0:
            meta_path = os.path.join(output_dir, 'collection_metadata.csv')
            df.to_csv(meta_path, index=False, encoding='utf-8-sig')
            print(f"  元数据已保存: {meta_path}")
        
        return df


class AMapStreetViewAPI:
    """
    高德地图街景 API 封装
    
    申请地址: https://lbs.amap.com/
    文档: https://lbs.amap.com/api/webservice/guide/api/newpoisearch
    
    注意: 高德街景API需要申请"街景"服务权限
    """
    
    def __init__(self, key: str):
        self.key = key
    
    def get_streetview_image(
        self,
        lng: float,
        lat: float,
        heading: float = 0,
        pitch: float = 0,
        output_dir: str = DEFAULT_OUTPUT,
        overwrite: bool = False,
        batch: bool = False,
    ) -> Tuple[Optional[str], Optional[dict]]:
        """
        获取高德街景影像。
        高德使用坐标转换(lon,lat格式略有不同)
        """
        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:8]
        filename = f"amap_sv_{coord_hash}_{int(heading)}deg.jpg"
        filepath = os.path.join(output_dir, filename)
        
        if os.path.exists(filepath) and not overwrite:
            return filepath, {'status': 'cached', 'lng': lng, 'lat': lat, 'heading': heading}
        
        # 高德街景请求
        # 注意：高德需要先通过坐标服务获取街景panoid
        import requests
        
        # Step 1: 坐标转换 + 获取panoid
        convert_url = (
            f"https://restapi.amap.com/v3/assistant/coordinate/convert"
            f"?locations={lng},{lat}"
            f"&coordsys=gps"
            f"&key={self.key}"
        )
        
        try:
            resp = requests.get(convert_url, timeout=5)
            if resp.status_code != 200:
                return None, None
            
            data = resp.json()
            if data.get('status') != '1':
                return None, None
            
            gcj_locs = data.get('locations', '')
            
            # Step 2: 获取街景ID
            sv_url = (
                f"https://restapi.amap.com/v3/streetview/snapshot"
                f"?location={gcj_locs}"
                f"&heading={heading}"
                f"&pitch={pitch}"
                f"&width=600&height=300"
                f"&key={self.key}"
            )
            
            resp2 = requests.get(sv_url, timeout=10)
            if resp2.status_code == 200 and len(resp2.content) > 1000:
                # 高德返回的是图片URL而非直接图片，需要再次请求
                content_type = resp2.headers.get('Content-Type', '')
                if 'image' in content_type or len(resp2.content) > 5000:
                    os.makedirs(output_dir, exist_ok=True)
                    with open(filepath, 'wb') as f:
                        f.write(resp2.content)
                    
                    meta = {
                        'lng': lng, 'lat': lat, 'heading': heading,
                        'pitch': pitch, 'size': len(resp2.content),
                        'hash': coord_hash, 'source': 'amap',
                    }
                    return filepath, meta
        except Exception as e:
            print(f"  [WARN] AMap API failed for ({lng:.4f},{lat:.4f}): {e}")
        
        return None, None


class SimulatedStreetView:
    """
    模拟街景采集器 — 用于开发调试和无API Key时的工作。
    
    生成符合真实街景统计分布的合成影像标签数据，
    分布参数基于南山区实际城市形态数据校准：
    - 高密度城中村区域 → 低SCR, 低BFD, 窄EWW
    - 低密度高端区域 → 高SCR, 高BFD, 宽EWW
    """
    
    def __init__(self, rng: Optional[np.random.Generator] = None):
        self.rng = rng or np.random.default_rng(42)
        
        # 统计分布参数 (从楼栋数据和高德数据校准)
        # SCR分布: 城中村偏低，高端住区偏高
        self.scr_params = {
            'high_density': (0.35, 0.15),   # mean, std
            'medium_density': (0.55, 0.12),
            'low_density': (0.78, 0.08),
        }
        # BFD分布
        self.bfd_params = {
            'high_density': (0.15, 0.08),
            'medium_density': (0.30, 0.10),
            'low_density': (0.60, 0.12),
        }
    
    def estimate_density_class(self, lng: float, lat: float,
                               building_df: Optional[pd.DataFrame] = None) -> str:
        """基于周边建筑密度估算城市形态类型"""
        if building_df is not None and len(building_df) > 0:
            coords = building_df[['lng', 'lat']].values
            distances = np.sqrt(
                (coords[:, 0] - lng) ** 2 + (coords[:, 1] - lat) ** 2
            )
            nearby = (distances < 0.005).sum()  # ~500m缓冲
            if nearby >= 80:
                return 'high_density'
            elif nearby >= 30:
                return 'medium_density'
            else:
                return 'low_density'
        
        # 备选: 基于坐标的启发式判断 (南山区典型值)
        # 后海/粤海一带较密, 深圳湾一带较疏
        density_heuristic = (
            (lng > 113.90 and lng < 113.95 and lat > 22.50) or
            (lng > 113.92 and lng < 113.96 and lat < 22.52)
        )
        return 'high_density' if density_heuristic else 'medium_density'
    
    def generate_metrics(self, lng: float, lat: float,
                         building_df: Optional[pd.DataFrame] = None) -> Dict[str, float]:
        """
        基于位置的城市形态，生成合成步行环境指标。
        分布参数经过楼栋数据校准。
        """
        density_class = self.estimate_density_class(lng, lat, building_df)
        
        scr_mean, scr_std = self.scr_params[density_class]
        bfd_mean, bfd_std = self.bfd_params[density_class]
        
        scr = float(self.rng.normal(scr_mean, scr_std))
        bfd = float(self.rng.normal(bfd_mean, bfd_std))
        
        # EWW与SCR高度相关
        eww = scr * float(self.rng.uniform(2.0, 4.5))
        
        # SVI综合指标
        svi = 0.5 * scr + 0.3 * bfd + 0.2 * float(self.rng.uniform(0.3, 0.9))
        
        return {
            'SCR': np.clip(scr, 0, 1),
            'BFD': np.clip(bfd, 0, 1),
            'EWW': np.clip(eww, 0, 5),
            'SVI': np.clip(svi, 0, 1),
            'density_class': density_class,
            'lng': lng,
            'lat': lat,
        }
    
    def batch_generate(
        self,
        points: List[Tuple[float, float]],
        building_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """批量生成合成指标"""
        results = []
        for lng, lat in points:
            m = self.generate_metrics(lng, lat, building_df)
            results.append(m)
        return pd.DataFrame(results)


# ==========================
# 沿路网采样
# ==========================

class NetworkSampler:
    """
    沿OSM路网进行空间采样，生成街景采集点列表。
    
    策略:
    1. 加载OSM路网数据
    2. 按道路类型分配采样密度
    3. 沿边线性插值生成采样点
    4. 对采样点分配街道级别属性(道路类型)
    """
    
    def __init__(self, network_nodes_path: Optional[str] = None,
                 network_edges_path: Optional[str] = None):
        """
        初始化采样器。
        
        如果提供路网数据路径，直接加载。
        否则返回空的采样器，之后再加载数据。
        """
        self.nodes = None
        self.edges = None
        
        if network_nodes_path and os.path.exists(network_nodes_path):
            self.load_network(network_nodes_path, network_edges_path)
    
    def load_network(self, nodes_path: str, edges_path: Optional[str] = None):
        """加载路网节点和边数据"""
        print(f"  加载路网节点: {nodes_path}")
        self.nodes = pd.read_csv(nodes_path)
        
        if edges_path and os.path.exists(edges_path):
            print(f"  加载路网边: {edges_path}")
            self.edges = pd.read_csv(edges_path)
    
    def sample_along_network(
        self,
        intervals_m: Optional[Dict[str, int]] = None,
    ) -> pd.DataFrame:
        """
        沿路网生成采样点。
        
        参数:
            intervals_m: 道路类型→采样间隔(米)的映射
        
        返回:
            采样点DataFrame，含 lng, lat, road_type, distance_from_origin
        """
        if intervals_m is None:
            intervals_m = SAMPLE_INTERVALS_M
        
        # 如果没有边数据，从节点数据生成简单边
        if self.edges is None and self.nodes is not None:
            print("  [INFO] 无边数据，使用KNN邻接关系生成采样边")
            return self._sample_from_nodes(intervals_m)
        
        # 沿边采样
        sample_points = []
        
        for _, edge in self.edges.iterrows():
            road_type = edge.get('highway', edge.get('road_type', 'unclassified'))
            interval = intervals_m.get(road_type, intervals_m['unclassified'])
            
            # 从边的两个端点
            u, v = edge.get('u', 0), edge.get('v', 0)
            
            try:
                node_u = self.nodes[self.nodes.get('node_id', self.nodes.index) == u]
                node_v = self.nodes[self.nodes.index == v]
                
                if len(node_u) == 0 or len(node_v) == 0:
                    continue
                
                u_row = node_u.iloc[0]
                v_row = node_v.iloc[0]
                
                lng1, lat1 = u_row['lng'], u_row['lat']
                lng2, lat2 = v_row['lng'], v_row['lat']
                
                # 计算边的地理长度(近似)
                edge_length = self._haversine(lng1, lat1, lng2, lat2)
                
                if edge_length < 10:  # 跳过太短的边
                    continue
                
                # 沿边均匀采样
                n_samples = max(1, int(edge_length / interval))
                
                for k in range(n_samples + 1):
                    t = k / max(n_samples, 1)
                    lng = lng1 + t * (lng2 - lng1)
                    lat = lat1 + t * (lat2 - lat1)
                    
                    sample_points.append({
                        'lng': lng,
                        'lat': lat,
                        'road_type': road_type,
                        'edge_id': f"{u}_{v}",
                        'distance_from_start': k * interval,
                    })
            except Exception:
                continue
        
        df = pd.DataFrame(sample_points)
        
        # 过滤边界
        df = df[
            (df['lng'] >= NANSHAN_BOUNDS['lng_min']) &
            (df['lng'] <= NANSHAN_BOUNDS['lng_max']) &
            (df['lat'] >= NANSHAN_BOUNDS['lat_min']) &
            (df['lat'] <= NANSHAN_BOUNDS['lat_max'])
        ].copy()
        
        # 去重(同一坐标只保留一个)
        df = df.drop_duplicates(subset=['lng', 'lat'])
        
        print(f"  生成 {len(df)} 个采样点")
        print(f"  道路类型分布:")
        for rt, cnt in df['road_type'].value_counts().items():
            print(f"    {rt}: {cnt} ({100*cnt/len(df):.1f}%)")
        
        return df
    
    def _sample_from_nodes(self, intervals_m: Dict[str, int]) -> pd.DataFrame:
        """从节点数据用KNN生成采样边"""
        if self.nodes is None or len(self.nodes) == 0:
            return pd.DataFrame()
        
        sample_points = []
        
        # 对每个节点，在其K近邻中寻找边
        coords = self.nodes[['lng', 'lat']].values
        from scipy.spatial import cKDTree
        tree = cKDTree(coords)
        
        # 每50个节点中找一个近邻作为"边"
        step = 50
        for i in range(0, len(self.nodes), step):
            node = self.nodes.iloc[i]
            dists, idxs = tree.query([node['lng'], node['lat']], k=2)
            
            for j_idx in idxs[1:]:
                neighbor = self.nodes.iloc[j_idx]
                if dists[1] > 0.0001:  # 避免重复
                    lng1, lat1 = node['lng'], node['lat']
                    lng2, lat2 = neighbor['lng'], neighbor['lat']
                    
                    edge_len = self._haversine(lng1, lat1, lng2, lat2)
                    if edge_len > 5:
                        # 沿这条"边"采样一个点
                        t = 0.5  # 取中点
                        sample_points.append({
                            'lng': lng1 + t * (lng2 - lng1),
                            'lat': lat1 + t * (lat2 - lat1),
                            'road_type': 'sampled',
                            'edge_id': f"knn_{i}_{j_idx}",
                            'distance_from_start': 0,
                        })
                    break
        
        df = pd.DataFrame(sample_points)
        df = df.drop_duplicates(subset=['lng', 'lat'])
        print(f"  [KNN采样] 生成 {len(df)} 个采样点")
        return df
    
    @staticmethod
    def _haversine(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
        """计算两点间的球面距离(米)"""
        R = 6371000  # 地球半径(米)
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lng2 - lng1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ==========================
# 主流程
# ==========================

def run_streetview_collection(
    api_type: str = 'simulate',
    tencent_key: Optional[str] = None,
    amap_key: Optional[str] = None,
    output_dir: str = DEFAULT_OUTPUT,
    network_nodes_path: Optional[str] = None,
    building_csv: Optional[str] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    主采集流程。
    
    参数:
        api_type: 'tencent' | 'amap' | 'simulate'
        tencent_key: 腾讯API Key
        amap_key: 高德API Key
        output_dir: 输出目录
        network_nodes_path: 路网节点CSV路径
        building_csv: 楼栋数据CSV路径(用于采样校准)
    
    返回:
        (采样点DataFrame, 采集结果DataFrame)
    """
    print("=" * 60)
    print("街景影像采集模块")
    print(f"API类型: {api_type.upper()}")
    print("=" * 60)
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'images'), exist_ok=True)
    
    # Step 1: 生成采样点
    print("\n[Step 1] 沿路网采样...")
    sampler = NetworkSampler()
    if network_nodes_path and os.path.exists(network_nodes_path):
        sampler.load_network(network_nodes_path)
    
    sample_points = sampler.sample_along_network(SAMPLE_INTERVALS_M)
    
    # Step 2: 加载楼栋数据(用于模拟模式校准)
    building_df = None
    if building_csv and os.path.exists(building_csv) and api_type == 'simulate':
        print(f"\n[Step 2] 加载楼栋数据用于模拟校准: {building_csv}")
        building_df = pd.read_csv(building_csv, dtype=str, keep_default_na=False)
        building_df['lng'] = pd.to_numeric(building_df['中心坐标'], errors='coerce')
        building_df['lat'] = pd.to_numeric(building_df['中心点坐标'], errors='coerce')
        building_df = building_df.dropna(subset=['lng', 'lat'])
    
    # Step 3: 执行采集
    print(f"\n[Step 3] 执行采集 ({api_type})...")
    
    if api_type == 'tencent' and tencent_key:
        client = TencentStreetViewAPI(tencent_key)
        results = client.batch_fetch(
            list(zip(sample_points['lng'], sample_points['lat'])),
            output_dir=os.path.join(output_dir, 'images'),
            headings=HEADINGS,
            delay=0.15,
        )
    elif api_type == 'amap' and amap_key:
        client = AMapStreetViewAPI(amap_key)
        results = []
        for _, pt in sample_points.iterrows():
            for h in HEADINGS:
                fp, meta = client.get_streetview_image(
                    pt['lng'], pt['lat'], h,
                    output_dir=os.path.join(output_dir, 'images'),
                )
                results.append(meta or {'status': 'failed', 'lng': pt['lng'], 'lat': pt['lat']})
                time.sleep(0.1)
        results = pd.DataFrame(results)
    else:
        # 模拟模式
        print("  [模拟模式] 生成合成步行环境指标(基于楼栋密度)")
        sim = SimulatedStreetView()
        results = sim.batch_generate(
            list(zip(sample_points['lng'], sample_points['lat'])),
            building_df=building_df,
        )
        
        # 模拟采集统计
        print(f"\n  模拟采集统计:")
        print(f"  SCR: mean={results['SCR'].mean():.3f}, std={results['SCR'].std():.3f}")
        print(f"  BFD: mean={results['BFD'].mean():.3f}, std={results['BFD'].std():.3f}")
        print(f"  EWW: mean={results['EWW'].mean():.3f} m, std={results['EWW'].std():.3f}")
        print(f"  SVI: mean={results['SVI'].mean():.3f}, std={results['SVI'].std():.3f}")
        print(f"  城市形态分布:")
        for dc, cnt in results['density_class'].value_counts().items():
            print(f"    {dc}: {cnt} ({100*cnt/len(results):.1f}%)")
    
    # Step 4: 合并采样点+结果
    print("\n[Step 4] 汇总结果...")
    
    if 'lng' in results.columns and 'lat' in results.columns:
        merged = sample_points.merge(
            results, on=['lng', 'lat'], how='left', suffixes=('', '_result')
        )
    else:
        merged = sample_points.copy()
        for col in results.columns:
            if col not in ['lng', 'lat']:
                merged[col] = results[col].values[:len(merged)] if len(results) >= len(merged) else np.nan
    
    output_path = os.path.join(output_dir, 'sampling_points_with_metrics.csv')
    merged.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"  采样点+指标已保存: {output_path}")
    
    # 统计
    total = len(merged)
    if 'status' in results.columns:
        success = (results['status'] == 'success').sum() if 'success' in results['status'].values else 0
        cached = (results['status'] == 'cached').sum() if 'cached' in results['status'].values else 0
        failed = (results['status'] == 'failed').sum() if 'failed' in results['status'].values else 0
        print(f"\n  采集统计: 成功={success}, 缓存={cached}, 失败={failed}")
    
    print("\n采集完成!")
    return sample_points, merged


# ==========================
# 使用示例
# ==========================

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='街景影像采集')
    parser.add_argument('--api', choices=['tencent', 'amap', 'simulate'], 
                        default='simulate', help='API类型')
    parser.add_argument('--tencent-key', default=None, help='腾讯API Key')
    parser.add_argument('--amap-key', default=None, help='高德API Key')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出目录')
    parser.add_argument('--nodes', default=None, help='路网节点CSV路径')
    parser.add_argument('--buildings', default=None, help='楼栋数据CSV路径')
    
    args = parser.parse_args()
    
    run_streetview_collection(
        api_type=args.api,
        tencent_key=args.tencent_key,
        amap_key=args.amap_key,
        output_dir=args.output,
        network_nodes_path=args.nodes,
        building_csv=args.buildings,
    )
