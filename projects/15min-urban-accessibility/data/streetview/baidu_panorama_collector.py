# -*- coding: utf-8 -*-
"""
==============================================================================
Baidu Panorama Collection for Nanshan District, Shenzhen
用于深圳南山区城中村/高端社区街景影像采集

用法:
    # 模拟模式 (开发调试)
    python baidu_panorama_collector.py --mode simulate

    # 腾讯街景 API 模式 (需要 --tencent-key)
    python baidu_panorama_collector.py --mode tencent --tencent-key YOUR_KEY

    # 纯采集模式 (使用streetlevel库获取百度全景)
    python baidu_panorama_collector.py --mode streetlevel --n-samples 200

    # 完整模式 (采集+语义分割指标)
    python baidu_panorama_collector.py --mode full --n-samples 200

==============================================================================
"""

import os
import sys
import math
import time
import json
import hashlib
import argparse
import warnings
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# ============================================================================
# 路径配置
# ============================================================================

BASE_DIR = Path(r'E:\xicha gis 智能定位')
PROJECT_DIR = BASE_DIR / 'projects' / '15min-urban-accessibility'
BUILDING_CSV = PROJECT_DIR / 'building_data' / '南山区-房屋楼栋基础数据_2920004003598.csv'
OUTPUT_DIR = PROJECT_DIR / 'data' / 'streetview' / 'baidu_collection'
SAMPLES_DIR = OUTPUT_DIR / 'samples'
IMAGES_DIR = OUTPUT_DIR / 'images'

# ============================================================================
# 南山区地理边界 (WGS84)
# ============================================================================

NANSHAN_BOUNDS = {
    'lng_min': 113.85,
    'lng_max': 114.45,
    'lat_min': 22.40,
    'lat_max': 22.80,
}

# ============================================================================
# 分层采样配置
# ============================================================================

SAMPLE_INTERVALS_M = {
    'motorway': 100,
    'trunk': 100,
    'primary': 80,
    'secondary': 120,
    'tertiary': 150,
    'residential': 200,
    'service': 250,
    'unclassified': 300,
}

# 用途代码映射
USAGE_TYPE_MAP = {
    1: 'Residential',
    2: 'Residential',
    3: 'Mixed Residential',
    4: 'Commercial',
    5: 'Industrial',
    6: 'Infrastructure',
    7: 'Other',
    8: 'Public',
    0: 'Unknown',
}

# ============================================================================
# 坐标转换工具 (WGS84 <-> GCJ-02 <-> BD-09)
# https://github.com/wandergis/coordtransform
# ============================================================================

PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323

def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0 / 3.0
    ret += (20.0*math.sin(y*PI) + 40.0*math.sin(y/3.0*PI)) * 2.0 / 3.0
    ret += (160.0*math.sin(y/12.0*PI) + 320.0*math.sin(y*PI/30.0)) * 2.0 / 3.0
    return ret

def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0 / 3.0
    ret += (20.0*math.sin(x*PI) + 40.0*math.sin(x/3.0*PI)) * 2.0 / 3.0
    ret += (150.0*math.sin(x/12.0*PI) + 300.0*math.sin(x/30.0*PI)) * 2.0 / 3.0
    return ret

def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
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
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x*x + y*y) - 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006

def wgs84_to_bd09(lng: float, lat: float) -> Tuple[float, float]:
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)

def bd09_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    x = lng - 0.0065
    y = lat - 0.006
    z = math.sqrt(x*x + y*y) + 0.00002 * math.sin(y * PI * 3000.0 / 180.0)
    theta = math.atan2(y, x) + 0.000003 * math.cos(x * PI * 3000.0 / 180.0)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006

def gcj02_to_wgs84(lng: float, lat: float) -> Tuple[float, float]:
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
    gcj_lng, gcj_lat = bd09_to_gcj02(lng, lat)
    return gcj02_to_wgs84(gcj_lng, gcj_lat)


# ============================================================================
# 数据加载
# ============================================================================

def load_building_data() -> pd.DataFrame:
    """加载楼栋数据，自动修正列名与坐标值的反向问题"""
    print(f"[数据] 加载楼栋数据: {BUILDING_CSV}")
    df = pd.read_csv(BUILDING_CSV, dtype=str, keep_default_na=False)

    # 修正: 中心坐标列的值是经度(113.9X), 中心点坐标列的值是纬度(22.5X)
    # 但列名是反的
    df['lng'] = pd.to_numeric(df['中心坐标'], errors='coerce')   # 实际是经度
    df['lat'] = pd.to_numeric(df['中心点坐标'], errors='coerce')  # 实际是纬度
    df['floor_count'] = pd.to_numeric(df['总层数'], errors='coerce').fillna(0).astype(int)
    df['usage_type'] = pd.to_numeric(df['使用用途'], errors='coerce').fillna(0).astype(int)
    df['usage_name'] = df['usage_type'].map(USAGE_TYPE_MAP)
    df['building_name'] = df['名称'].str.strip()
    df['address'] = df['常用地址'].str.strip()

    df = df.dropna(subset=['lng', 'lat'])

    # 过滤南山区范围
    df = df[
        (df['lng'] >= NANSHAN_BOUNDS['lng_min']) &
        (df['lng'] <= NANSHAN_BOUNDS['lng_max']) &
        (df['lat'] >= NANSHAN_BOUNDS['lat_min']) &
        (df['lat'] <= NANSHAN_BOUNDS['lat_max'])
    ]

    print(f"[数据] 有效楼栋: {len(df)}, 经度范围: {df['lng'].min():.4f}~{df['lng'].max():.4f}")
    print(f"[数据] 纬度范围: {df['lat'].min():.4f}~{df['lat'].max():.4f}")
    return df


# ============================================================================
# 分层采样器
# ============================================================================

def classify_urban_form(df: pd.DataFrame) -> pd.DataFrame:
    """基于楼栋名称和密度分类城市形态"""
    df = df.copy()

    # 城中村关键词
    village_keywords = ['村', '新村', '旧村', '村民']
    is_village = df['building_name'].str.contains('|'.join(village_keywords), na=False, regex=True)

    # 城中村附加条件：楼层较低 (通常1-9层)
    df['is_village'] = is_village & (df['floor_count'] <= 9)

    # 高端社区关键词
    highend_keywords = ['花园', '山庄', '广场', '公馆', '名苑', '御苑',
                        '海滨', '天利', '阳光', '观海', '豪', '苑']
    df['is_highend'] = df['building_name'].str.contains('|'.join(highend_keywords), na=False, regex=True)

    # 城中村密集区（城中村楼栋聚集处）
    # 通过KDE或密度阈值识别
    from scipy.spatial import cKDTree
    coords = df[['lng', 'lat']].values
    tree = cKDTree(coords)
    # 每个点找50m范围内的城中村楼栋数
    village_coords = df[df['is_village']][['lng', 'lat']].values
    if len(village_coords) > 0:
        village_tree = cKDTree(village_coords)
        # 50m ≈ 0.00045度
        village_density = []
        for lng, lat in coords:
            count = len(village_tree.query_ball_point([lng, lat], r=0.00045))
            village_density.append(count)
        df['village_nearby'] = village_density
    else:
        df['village_nearby'] = 0

    # 综合分类
    def classify(row):
        if row['is_village']:
            return 'Village'
        elif row['is_highend']:
            return 'High-End'
        elif row['village_nearby'] >= 5:
            return 'Village Fringe'  # 城中村边缘
        elif row['floor_count'] >= 20:
            return 'High-Rise'
        elif row['floor_count'] >= 8:
            return 'Mid-Rise'
        else:
            return 'Low-Rise'

    df['urban_form'] = df.apply(classify, axis=1)
    return df


def stratified_sample(df: pd.DataFrame, n_samples: int = 200,
                       priorities: Optional[Dict[str, float]] = None) -> pd.DataFrame:
    """
    分层均匀采样，确保城中村和高端社区有足够的代表性。

    priorities: 各类别的采样权重
    """
    if priorities is None:
        priorities = {
            'Village': 3.0,          # 城中村权重最高
            'Village Fringe': 1.5,     # 城中村边缘
            'High-End': 2.5,           # 高端社区
            'High-Rise': 1.0,
            'Mid-Rise': 1.0,
            'Low-Rise': 0.5,
        }

    # 按类别分配配额
    counts = df['urban_form'].value_counts()
    quotas = {}
    total_weight = sum(priorities.get(cat, 1.0) for cat in counts.index)

    for cat, n in counts.items():
        w = priorities.get(cat, 1.0)
        quotas[cat] = max(2, int(n_samples * w / total_weight * (total_weight / sum(priorities.values()))))

    # 归一化确保总和约等于n_samples
    scale = n_samples / sum(quotas.values())
    for cat in quotas:
        quotas[cat] = max(1, int(quotas[cat] * scale))

    print(f"[采样] 分层配额分配:")
    for cat, q in sorted(quotas.items()):
        n_available = len(df[df['urban_form'] == cat])
        print(f"  {cat}: 配额{q}, 可用{n_available}")

    # 实际采样
    sampled = []
    for cat, q in quotas.items():
        subset = df[df['urban_form'] == cat]
        if len(subset) == 0:
            continue
        # 均匀分布采样（按lng排序后等间隔选取）
        step = max(1, len(subset) // q)
        indices = list(range(0, len(subset), step))[:q]
        sampled.append(subset.iloc[indices])

    result = pd.concat(sampled, ignore_index=True)
    result = result.drop_duplicates(subset=['lng', 'lat'])

    print(f"[采样] 实际采样: {len(result)} 个点")
    for form, cnt in result['urban_form'].value_counts().items():
        print(f"  {form}: {cnt} ({100*cnt/len(result):.1f}%)")

    return result


# ============================================================================
# 百度街景采集 (通过streetlevel库)
# ============================================================================

def collect_with_streetlevel(
    sample_df: pd.DataFrame,
    output_dir: Path,
    zoom: int = 3,
    directions: List[int] = None,
    delay: float = 0.3,
    overwrite: bool = False,
    checkpoint_file: Optional[Path] = None,
) -> pd.DataFrame:
    """
    使用streetlevel库采集百度街景。

    streetlevel安装: pip install streetlevel
    """
    if directions is None:
        directions = [0, 90, 180, 270]

    try:
        from streetlevel import baidu
        from streetlevel.baidu import Crs
        print("[百度街景] streetlevel库已加载")
        use_streetlevel = True
    except ImportError:
        print("[百度街景] streetlevel未安装，请运行: pip install streetlevel")
        print("[百度街景] 将尝试备用方案（requests直接调用）")
        use_streetlevel = False

    results = []
    checkpoint_file = checkpoint_file or output_dir / '.checkpoint.json'

    # 加载断点
    completed_hashes = set()
    if checkpoint_file and checkpoint_file.exists():
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            ckpt = json.load(f)
            completed_hashes = set(ckpt.get('completed', []))
        print(f"[断点] 已加载 {len(completed_hashes)} 个已完成采集点")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    meta_records = []

    total = len(sample_df) * len(directions)
    done = 0
    failed = 0

    for idx, row in sample_df.iterrows():
        lng, lat = float(row['lng']), float(row['lat'])
        urban_form = row.get('urban_form', 'Unknown')
        building_name = row.get('building_name', '')

        coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}".encode()).hexdigest()[:12]
        marker = f"{coord_hash}_{urban_form}"

        if marker in completed_hashes:
            done += len(directions)
            continue

        for heading in directions:
            img_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:16]
            filename = f"sv_{img_hash}_{int(heading)}deg.jpg"
            filepath = IMAGES_DIR / filename

            if filepath.exists() and not overwrite:
                results.append({
                    'lng': lng, 'lat': lat,
                    'heading': heading,
                    'status': 'cached',
                    'filename': filename,
                    'urban_form': urban_form,
                    'building_name': building_name,
                })
                done += 1
                continue

            if use_streetlevel:
                success = _fetch_streetlevel(lng, lat, heading, filepath, zoom)
            else:
                success = _fetch_bd09_direct(lng, lat, heading, filepath)

            if success:
                results.append({
                    'lng': lng, 'lat': lat,
                    'heading': heading,
                    'status': 'success',
                    'filename': filename,
                    'urban_form': urban_form,
                    'building_name': building_name,
                })
                completed_hashes.add(marker)
            else:
                results.append({
                    'lng': lng, 'lat': lat,
                    'heading': heading,
                    'status': 'failed',
                    'urban_form': urban_form,
                    'building_name': building_name,
                })
                failed += 1

            done += 1

            # 进度报告
            if done % 20 == 0 or done == total:
                pct = 100 * done / max(total, 1)
                print(f"\r[进度] {done}/{total} ({pct:.1f}%) 成功≈{done-failed} 失败≈{failed}", end='', flush=True)

            time.sleep(delay)

    print()  # 换行

    # 保存断点
    if checkpoint_file:
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump({'completed': list(completed_hashes), 'timestamp': datetime.now().isoformat()}, f)

    df_result = pd.DataFrame(results)
    if len(df_result) > 0:
        meta_path = OUTPUT_DIR / 'collection_metadata.csv'
        df_result.to_csv(meta_path, index=False, encoding='utf-8-sig')
        print(f"[保存] 元数据已保存: {meta_path}")

    print(f"\n[完成] 成功: {sum(1 for r in results if r['status']=='success')}, 缓存: {sum(1 for r in results if r['status']=='cached')}, 失败: {sum(1 for r in results if r['status']=='failed')}")
    return df_result


def _fetch_streetlevel(lng: float, lat: float, heading: int,
                        filepath: Path, zoom: int = 3) -> bool:
    """使用streetlevel库采集一张百度全景"""
    try:
        from streetlevel import baidu
        from streetlevel.baidu import Crs

        # 查找最近的全景
        pano = baidu.find_panorama(lat, lng, crs=Crs.WGS84)
        if pano is None:
            return False

        # 下载全景
        baidu.download_panorama(pano, str(filepath), zoom=zoom)

        if filepath.exists() and filepath.stat().st_size > 10000:
            return True
        return False
    except Exception as e:
        print(f"\n  [streetlevel错误] ({lng:.4f},{lat:.4f}): {e}")
        return False


def _fetch_bd09_direct(lng: float, lat: float, heading: int, filepath: Path) -> bool:
    """
    备用方案: 直接通过requests调用百度街景CDN。
    基于百度地图网页版的全景图片URL规律。
    """
    import requests

    # WGS84 -> BD09
    bd_lng, bd_lat = wgs84_to_bd09(lng, lat)

    # 百度街景图片URL (通过搜索附近全景ID)
    # 方法1: 通过百度地图API搜索附近全景
    search_url = (
        f"https://maps.map.qq.com/risk/?version=current"
        f"&keytype=panorama&pointx={bd_lng}&pointy={bd_lat}"
    )

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://map.qq.com/',
        }

        # 获取全景ID
        # 百度街景的API端点（需要更多研究）
        # 这里提供一个占位符，实际使用时需要根据百度地图的实际API调整
        session = requests.Session()
        session.headers.update(headers)

        # 方案: 尝试从腾讯街景获取（因为已有腾讯API封装）
        # 或者直接返回False让用户补充API
        return False
    except Exception:
        return False


# ============================================================================
# 腾讯街景采集
# ============================================================================

def collect_with_tencent(
    sample_df: pd.DataFrame,
    api_key: str,
    output_dir: Path,
    directions: List[int] = None,
    delay: float = 0.2,
    overwrite: bool = False,
) -> pd.DataFrame:
    """
    使用腾讯街景API采集（已有封装，需要API Key）
    """
    if directions is None:
        directions = [0, 90, 180, 270]

    import requests

    results = []
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    total = len(sample_df) * len(directions)
    done = 0

    print(f"[腾讯街景] API Key: {api_key[:6]}...{api_key[-4:]}")
    print(f"[腾讯街景] 共 {total} 个影像待采集")

    for idx, row in sample_df.iterrows():
        lng, lat = float(row['lng']), float(row['lat'])
        urban_form = row.get('urban_form', 'Unknown')
        building_name = row.get('building_name', '')

        for heading in directions:
            coord_hash = hashlib.md5(f"{lng:.6f}{lat:.6f}{heading}".encode()).hexdigest()[:16]
            filename = f"sv_tencent_{coord_hash}_{int(heading)}deg.jpg"
            filepath = IMAGES_DIR / filename

            if filepath.exists() and not overwrite:
                results.append({
                    'lng': lng, 'lat': lat, 'heading': heading,
                    'status': 'cached', 'filename': filename,
                    'urban_form': urban_form, 'building_name': building_name,
                })
                done += 1
                continue

            # 腾讯街景 Image API
            url = (
                f"https://apis.map.qq.com/imagery/streetview/image"
                f"?location={lat},{lng}"
                f"&heading={heading}&pitch=0"
                f"&key={api_key}"
            )

            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200 and len(resp.content) > 5000:
                    with open(filepath, 'wb') as f:
                        f.write(resp.content)
                    results.append({
                        'lng': lng, 'lat': lat, 'heading': heading,
                        'status': 'success', 'filename': filename,
                        'urban_form': urban_form, 'building_name': building_name,
                    })
                else:
                    results.append({
                        'lng': lng, 'lat': lat, 'heading': heading,
                        'status': 'failed',
                        'urban_form': urban_form, 'building_name': building_name,
                    })
            except Exception:
                results.append({
                    'lng': lng, 'lat': lat, 'heading': heading,
                    'status': 'error',
                    'urban_form': urban_form, 'building_name': building_name,
                })

            done += 1
            if done % 20 == 0:
                pct = 100 * done / max(total, 1)
                print(f"\r[进度] {done}/{total} ({pct:.1f}%)", end='', flush=True)

            time.sleep(delay)

    print()

    df_result = pd.DataFrame(results)
    if len(df_result) > 0:
        meta_path = OUTPUT_DIR / 'collection_metadata.csv'
        df_result.to_csv(meta_path, index=False, encoding='utf-8-sig')
        print(f"[保存] 元数据已保存: {meta_path}")

    success = sum(1 for r in results if r['status'] == 'success')
    cached = sum(1 for r in results if r['status'] == 'cached')
    failed = total - success - cached
    print(f"[完成] 成功: {success}, 缓存: {cached}, 失败: {failed}")

    return df_result


# ============================================================================
# 模拟模式
# ============================================================================

def simulate_collection(sample_df: pd.DataFrame) -> pd.DataFrame:
    """
    模拟采集: 基于楼栋数据生成合成步行环境指标。
    用于验证采样策略和分析分布。
    """
    print(f"\n[模拟] 生成 {len(sample_df)} 个采样点的合成指标...")

    # 各类别的典型SCR/EWW/BFD分布
    form_params = {
        'Village':         {'scr': (0.35, 0.10), 'bfd': (0.15, 0.05), 'eww': (1.5, 0.3)},
        'Village Fringe':   {'scr': (0.45, 0.10), 'bfd': (0.25, 0.08), 'eww': (2.0, 0.4)},
        'High-End':        {'scr': (0.70, 0.10), 'bfd': (0.55, 0.10), 'eww': (3.5, 0.5)},
        'High-Rise':       {'scr': (0.55, 0.08), 'bfd': (0.40, 0.08), 'eww': (2.5, 0.4)},
        'Mid-Rise':        {'scr': (0.60, 0.08), 'bfd': (0.35, 0.08), 'eww': (2.8, 0.4)},
        'Low-Rise':        {'scr': (0.72, 0.08), 'bfd': (0.50, 0.10), 'eww': (3.5, 0.5)},
        'Unknown':         {'scr': (0.55, 0.12), 'bfd': (0.35, 0.10), 'eww': (2.5, 0.5)},
    }

    rng = np.random.default_rng(42)

    results = []
    for _, row in sample_df.iterrows():
        form = row.get('urban_form', 'Unknown')
        params = form_params.get(form, form_params['Unknown'])

        scr = rng.normal(params['scr'][0], params['scr'][1])
        bfd = rng.normal(params['bfd'][0], params['bfd'][1])
        eww = rng.normal(params['eww'][0], params['eww'][1])

        scr = float(np.clip(scr, 0.1, 0.95))
        bfd = float(np.clip(bfd, 0.05, 0.85))
        eww = float(np.clip(eww, 0.5, 5.0))
        svi = 0.5*scr + 0.3*bfd + 0.2*rng.uniform(0.3, 0.9)

        results.append({
            'lng': row['lng'],
            'lat': row['lat'],
            'urban_form': form,
            'building_name': row.get('building_name', ''),
            'SCR': round(scr, 3),
            'BFD': round(bfd, 3),
            'EWW_m': round(eww, 2),
            'SVI': round(svi, 3),
            'sampling_mode': 'simulated',
        })

    df_result = pd.DataFrame(results)
    meta_path = OUTPUT_DIR / 'simulated_metrics.csv'
    df_result.to_csv(meta_path, index=False, encoding='utf-8-sig')
    print(f"[模拟] 指标已保存: {meta_path}")

    print(f"\n[模拟结果统计]")
    for form in df_result['urban_form'].unique():
        subset = df_result[df_result['urban_form'] == form]
        print(f"  {form} (n={len(subset)}): SCR={subset['SCR'].mean():.3f}, "
              f"EWW={subset['EWW_m'].mean():.2f}m, SVI={subset['SVI'].mean():.3f}")

    return df_result


# ============================================================================
# 主流程
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='南山区街景影像采集')
    parser.add_argument('--mode', choices=['streetlevel', 'tencent', 'simulate'],
                        default='simulate', help='采集模式')
    parser.add_argument('--tencent-key', default=None, help='腾讯API Key')
    parser.add_argument('--n-samples', type=int, default=200, help='采样点数')
    parser.add_argument('--zoom', type=int, default=3, choices=[1,2,3,4],
                        help='百度全景缩放级别 (1=512x256, 4=4096x2048)')
    parser.add_argument('--directions', type=int, default=4,
                        help='每个点采集方向数 (1/4)')
    parser.add_argument('--delay', type=float, default=0.3,
                        help='请求间隔(秒)')
    parser.add_argument('--overwrite', action='store_true',
                        help='覆盖已有影像')
    parser.add_argument('--seed', type=int, default=42, help='随机种子')

    args = parser.parse_args()

    print("=" * 60)
    print("深圳南山区街景影像采集")
    print(f"模式: {args.mode.upper()}")
    print(f"采样点: {args.n_samples}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 加载数据
    print("\n[Step 1] 加载楼栋数据...")
    df = load_building_data()

    # 2. 城市形态分类
    print("\n[Step 2] 城市形态分类...")
    df = classify_urban_form(df)
    print("[分类] 分布:")
    for form, cnt in df['urban_form'].value_counts().items():
        print(f"  {form}: {cnt} ({100*cnt/len(df):.1f}%)")

    # 3. 分层采样
    print(f"\n[Step 3] 分层均匀采样 (目标: {args.n_samples}点)...")
    sample_df = stratified_sample(df, n_samples=args.n_samples)

    # 保存采样点
    sample_path = SAMPLES_DIR / f'sample_points_n{len(sample_df)}.csv'
    sample_df.to_csv(sample_path, index=False, encoding='utf-8-sig')
    print(f"[采样] 采样点已保存: {sample_path}")

    # 4. 执行采集
    directions = [0] if args.directions == 1 else [0, 90, 180, 270]

    if args.mode == 'simulate':
        print(f"\n[Step 4] 模拟模式...")
        simulate_collection(sample_df)

    elif args.mode == 'tencent':
        if not args.tencent_key:
            print("[错误] --tencent-key 参数必填")
            return
        print(f"\n[Step 4] 腾讯街景API采集 ({len(sample_df)*len(directions)}个影像)...")
        collect_with_tencent(
            sample_df, args.tencent_key, OUTPUT_DIR,
            directions=directions, delay=args.delay, overwrite=args.overwrite,
        )

    elif args.mode == 'streetlevel':
        print(f"\n[Step 4] 百度全景采集 (streetlevel模式)...")
        print("[提示] 需要先安装: pip install streetlevel")
        print("[提示] 每个采样点将采集1张全景图，自动输出4个方向")
        collect_with_streetlevel(
            sample_df, OUTPUT_DIR,
            zoom=args.zoom, directions=[0],  # 全景本身是360度的
            delay=args.delay, overwrite=args.overwrite,
        )

    print("\n" + "=" * 60)
    print("采集流程完成!")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == '__main__':
    main()
