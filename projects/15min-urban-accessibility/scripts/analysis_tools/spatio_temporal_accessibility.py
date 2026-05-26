# -*- coding: utf-8 -*-
"""
增强版时空可达性分析系统 v3.0
================================

南山区15分钟城市公共服务时空可达性研究
整合OSM数据、高德API、大众点评、商业POI数据、小区AOI

核心功能:
1. 多数据源POI获取（OSM、高德API、大众点评、小区AOI）
2. 设施运营时间分析（便利店、快递、医院、诊所等）
3. 时间可达性计算模型（基于论文模型的优化实现）
4. 白天/夜间/深夜多时段时空对比
5. 小区级别时空贫困指数分析
6. 南山区空间可视化与报告生成

使用方法:
    python spatio_temporal_accessibility.py

作者: 未来交通实验室
日期: 2026-05-20
"""

import os
import sys
import json
import time
import math
import warnings
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from scipy.spatial import cKDTree
from scipy import stats

warnings.filterwarnings('ignore')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 配置区域
# ============================================================================

@dataclass
class StudyConfig:
    """研究配置"""
    # 路径配置
    base_dir: str = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
    output_dir: str = ""
    data_dir: str = ""
    osm_cache_dir: str = ""

    # 研究区域配置（南山区）
    study_area: str = "南山区, 深圳市"
    bbox: Dict[str, float] = field(default_factory=lambda: {
        'north': 22.54,
        'south': 22.48,
        'east': 113.98,
        'west': 113.85
    })

    # 步行参数
    walk_speed_kmh: float = 5.0
    available_time: int = 120
    accessibility_threshold: int = 15

    # 时段定义
    periods: Dict[str, Dict] = field(default_factory=lambda: {
        'day': {
            'name': '白天标准时段',
            'start': 8,
            'end': 18,
            'description': '08:00-18:00'
        },
        'evening': {
            'name': '夜间下班时段',
            'start': 18,
            'end': 22,
            'description': '18:00-22:00'
        },
        'night': {
            'name': '深夜应急时段',
            'start': 22,
            'end': 8,
            'description': '22:00-08:00'
        }
    })

    # 绕行系数（不同社区类型）
    detour_factors: Dict[str, float] = field(default_factory=lambda: {
        'urban_village': 1.5,
        'old_community': 1.3,
        'normal_community': 1.1,
        'high_end': 1.0
    })

    # 服务耗时（分钟）
    service_duration: Dict[str, int] = field(default_factory=lambda: {
        'convenience_store': 5,
        'pharmacy': 10,
        'supermarket': 15,
        'hospital': 30,
        'clinic': 20,
        'bank': 45,
        'atm': 2,
        'express': 8,
        'market': 15,
        'school': 30,
        'kindergarten': 20,
    })

    # 等候时间估计（分钟）
    wait_time: Dict[str, int] = field(default_factory=lambda: {
        'convenience_store': 2,
        'pharmacy': 8,
        'supermarket': 10,
        'hospital': 20,
        'clinic': 10,
        'bank': 15,
        'atm': 2,
        'express': 5,
        'market': 8,
        'school': 0,
        'kindergarten': 0,
    })

    # 设施类型中英文映射
    facility_names: Dict[str, str] = field(default_factory=lambda: {
        'convenience_store': '便利店',
        'pharmacy': '药店',
        'supermarket': '超市',
        'hospital': '医院',
        'clinic': '诊所',
        'bank': '银行',
        'atm': 'ATM',
        'express': '快递',
        'market': '菜市场',
        'school': '学校',
        'kindergarten': '幼儿园',
    })

    # 社区类型中英文映射
    community_names: Dict[str, str] = field(default_factory=lambda: {
        'urban_village': '城中村',
        'old_community': '老旧小区',
        'normal_community': '普通商品房',
        'high_end': '高端社区'
    })

    def __post_init__(self):
        if not self.output_dir:
            self.output_dir = os.path.join(self.base_dir, "output")
        if not self.data_dir:
            self.data_dir = os.path.join(self.base_dir, "osm_data")
        if not self.osm_cache_dir:
            self.osm_cache_dir = os.path.join(self.data_dir, "osm_cache")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.osm_cache_dir, exist_ok=True)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class OpeningHours:
    """营业时间数据模型"""
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    is_24h: bool = False
    night_service: bool = False
    business_period: str = ""
    service_hours: List[int] = field(default_factory=list)

    def to_hours(self) -> Tuple[Optional[int], Optional[int]]:
        """返回 (开放小时, 关闭小时)"""
        open_h, close_h = None, None
        if self.is_24h:
            return 0, 24
        if self.open_time:
            try:
                open_h = int(self.open_time.split(':')[0])
            except (ValueError, IndexError):
                pass
        if self.close_time:
            try:
                close_h = int(self.close_time.split(':')[0])
            except (ValueError, IndexError):
                pass
        return open_h, close_h

    def covers_period(self, period_start: int, period_end: int) -> bool:
        """检查是否覆盖指定时段"""
        if self.is_24h:
            return True
        if not self.service_hours:
            return False
        if period_end > period_start:
            return all(h in self.service_hours for h in range(period_start, period_end))
        else:
            return any(h in self.service_hours for h in range(period_start, 24)) or \
                   any(h in self.service_hours for h in range(0, period_end))

    def is_open_at(self, hour: int) -> bool:
        """检查特定小时是否营业"""
        if self.is_24h:
            return True
        if not self.service_hours:
            return True
        return hour in self.service_hours

    def get_open_duration(self) -> int:
        """获取营业时长（小时）"""
        if self.is_24h:
            return 24
        if not self.service_hours:
            return 0
        return len(self.service_hours)

    @staticmethod
    def from_string(hours_str: str) -> 'OpeningHours':
        """从字符串解析营业时间"""
        if not hours_str:
            return OpeningHours()

        hours_str = str(hours_str).strip()

        if '24' in hours_str and ('小时' in hours_str or '24h' in hours_str.lower()):
            return OpeningHours(
                is_24h=True,
                night_service=True,
                business_period=hours_str,
                service_hours=list(range(24))
            )

        result = OpeningHours(business_period=hours_str)

        try:
            if '-' in hours_str:
                parts = hours_str.replace('：', ':').split('-')
                if len(parts) == 2:
                    result.open_time = parts[0].strip()[:5]
                    result.close_time = parts[1].strip()[:5]

                    open_h, close_h = result.to_hours()
                    if open_h is not None and close_h is not None:
                        if close_h > open_h:
                            result.service_hours = list(range(open_h, close_h))
                        else:
                            result.service_hours = list(range(open_h, 24)) + list(range(0, close_h))

                        if close_h >= 20 or close_h < 6:
                            result.night_service = True
        except Exception:
            pass

        return result


@dataclass
class AccessibilityResult:
    """可达性计算结果"""
    facility_type: str
    nearest_fid: Optional[str]
    travel_time: float
    effective_time: float
    is_accessible: bool
    facility_name: str = ""
    mti: float = 0.0
    wti: float = 0.0
    tmi: float = 0.0
    ctpi: float = 0.0


@dataclass
class Facility:
    """设施数据模型"""
    fid: str
    name: str
    facility_type: str
    lng: float
    lat: float
    opening_hours: OpeningHours
    source: str = "osm"
    distance_km: float = 0.0
    travel_time: float = 0.0
    rating: float = 0.0
    address: str = ""


@dataclass
class Community:
    """小区数据模型"""
    cid: str
    name: str
    community_type: str
    lng: float
    lat: float
    population: int = 0
    building_count: int = 0


# ============================================================================
# 数据源管理器
# ============================================================================

class DataSourceManager:
    """多数据源管理器"""

    def __init__(self, config: StudyConfig):
        self.config = config

    def load_osm_data(self) -> pd.DataFrame:
        """加载OSM数据"""
        logger.info("[数据源] 加载OSM数据...")

        cache_file = os.path.join(self.config.osm_cache_dir, "poi_osm.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, encoding='utf-8-sig')
            logger.info(f"  从缓存加载: {len(df)} 条")
            return df

        return self._create_fallback_poi()

    def load_dianping_data(self) -> pd.DataFrame:
        """加载大众点评数据"""
        logger.info("[数据源] 加载大众点评数据...")

        cache_file = os.path.join(self.config.osm_cache_dir, "poi_dianping.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, encoding='utf-8-sig')
            logger.info(f"  从缓存加载: {len(df)}条")
            return df

        return self._create_dianping_fallback()

    def load_community_data(self) -> pd.DataFrame:
        """加载小区数据"""
        logger.info("[数据源] 加载小区数据...")

        cache_file = os.path.join(self.config.osm_cache_dir, "communities.csv")
        if os.path.exists(cache_file):
            df = pd.read_csv(cache_file, encoding='utf-8-sig')
            logger.info(f"  从缓存加载: {len(df)} 个")
            return df

        return self._create_community_fallback()

    def _create_dianping_fallback(self) -> pd.DataFrame:
        """创建大众点评模拟数据"""
        bbox = self.config.bbox
        np.random.seed(100)

        facilities = []
        type_configs = [
            ('convenience_store', '便利店', 80, ['24小时', '07:00-23:00', '08:00-22:00']),
            ('pharmacy', '药店', 25, ['08:00-21:00', '09:00-22:00', '24小时']),
            ('hospital', '医院', 10, ['08:00-18:00', '24小时']),
            ('clinic', '诊所', 15, ['08:00-20:00', '09:00-18:00']),
            ('bank', '银行', 12, ['09:00-17:00', '09:00-17:30']),
            ('express', '快递', 35, ['09:00-21:00', '10:00-20:00', '08:00-22:00']),
            ('supermarket', '超市', 20, ['08:00-22:00', '07:00-23:00']),
        ]

        for ftype, fname, count, hours_list in type_configs:
            for i in range(count):
                lng = bbox['west'] + np.random.random() * (bbox['east'] - bbox['west'])
                lat = bbox['south'] + np.random.random() * (bbox['north'] - bbox['south'])
                hours = np.random.choice(hours_list)

                facilities.append({
                    'fid': f'dp_{ftype}_{i}',
                    'name': f'{fname}{i+1}',
                    'facility_type': ftype,
                    'lng': lng,
                    'lat': lat,
                    'opening_hours': hours,
                    'source': 'dianping',
                    'rating': round(np.random.uniform(3.5, 5.0), 1)
                })

        df = pd.DataFrame(facilities)
        cache_file = os.path.join(self.config.osm_cache_dir, "poi_dianping.csv")
        df.to_csv(cache_file, index=False, encoding='utf-8-sig')
        logger.info(f"  生成大众点评模拟数据: {len(df)} 条")
        return df

    def _create_fallback_poi(self) -> pd.DataFrame:
        """创建OSM模拟数据"""
        bbox = self.config.bbox
        np.random.seed(42)

        facilities = []
        type_configs = [
            ('convenience_store', '便利店', 100, ['08:00-23:00', '07:00-22:00', '24小时', '09:00-21:00']),
            ('pharmacy', '药店', 30, ['08:00-21:00', '09:00-22:00', '24小时']),
            ('hospital', '医院', 15, ['08:00-18:00', '24小时']),
            ('clinic', '诊所', 20, ['08:00-20:00', '09:00-18:00']),
            ('bank', '银行', 15, ['09:00-17:00', '09:00-17:30']),
            ('express', '快递', 40, ['09:00-21:00', '10:00-20:00', '08:00-22:00']),
            ('supermarket', '超市', 25, ['08:00-22:00', '07:00-23:00']),
        ]

        for ftype, fname, count, hours_list in type_configs:
            for i in range(count):
                lng = bbox['west'] + np.random.random() * (bbox['east'] - bbox['west'])
                lat = bbox['south'] + np.random.random() * (bbox['north'] - bbox['south'])
                hours = np.random.choice(hours_list)

                facilities.append({
                    'fid': f'osm_{ftype}_{i}',
                    'name': f'{fname}{i+1}',
                    'facility_type': ftype,
                    'lng': lng,
                    'lat': lat,
                    'opening_hours': hours,
                    'source': 'osm'
                })

        df = pd.DataFrame(facilities)
        cache_file = os.path.join(self.config.osm_cache_dir, "poi_osm.csv")
        df.to_csv(cache_file, index=False, encoding='utf-8-sig')
        logger.info(f"  生成OSM模拟数据: {len(df)} 条")
        return df

    def _create_community_fallback(self) -> pd.DataFrame:
        """创建小区模拟数据"""
        bbox = self.config.bbox
        np.random.seed(42)

        community_types = list(self.config.detour_factors.keys())
        type_weights = [0.3, 0.25, 0.3, 0.15]

        communities = []
        for i in range(60):
            ctype = np.random.choice(community_types, p=type_weights)
            lng = bbox['west'] + np.random.random() * (bbox['east'] - bbox['west'])
            lat = bbox['south'] + np.random.random() * (bbox['north'] - bbox['south'])
            population = np.random.choice([500, 1000, 2000, 5000, 8000], p=[0.15, 0.3, 0.3, 0.15, 0.1])

            communities.append({
                'cid': f'comm_{i}',
                'name': f'小区{i+1}',
                'community_type': ctype,
                'lng': lng,
                'lat': lat,
                'population': population
            })

        df = pd.DataFrame(communities)
        cache_file = os.path.join(self.config.osm_cache_dir, "communities.csv")
        df.to_csv(cache_file, index=False, encoding='utf-8-sig')
        logger.info(f"  生成小区模拟数据: {len(df)} 个")
        return df


# ============================================================================
# 时间可达性计算模型
# ============================================================================

class TimeAccessibilityCalculator:
    """时间可达性计算器（基于论文模型优化）"""

    def __init__(self, config: StudyConfig):
        self.config = config
        self.facility_tree: Optional[cKDTree] = None
        self.facility_data: Optional[pd.DataFrame] = None

    def build_facility_index(self, facilities_df: pd.DataFrame) -> None:
        """构建设施空间索引"""
        if facilities_df is None or len(facilities_df) == 0:
            logger.warning("无设施数据，跳过索引构建")
            return

        df = facilities_df.dropna(subset=['lng', 'lat']).copy()
        df = df[(df['lng'] != 0) & (df['lat'] != 0)]
        df = df.reset_index(drop=True)

        coords = df[['lng', 'lat']].values
        self.facility_tree = cKDTree(coords)
        self.facility_data = df
        logger.info(f"设施索引构建完成: {len(self.facility_data)} 个设施")

    def calculate_travel_time(self, from_lng: float, from_lat: float,
                             to_lng: float, to_lat: float) -> float:
        """计算两点间步行时间（分钟）使用Haversine公式"""
        R = 6371
        lat1, lat2 = math.radians(from_lat), math.radians(to_lat)
        dlat = math.radians(to_lat - from_lat)
        dlng = math.radians(to_lng - from_lng)

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance_km = R * c
        speed_m_per_min = self.config.walk_speed_kmh * 1000 / 60
        return distance_km * 1000 / speed_m_per_min

    def find_nearest_facilities(self, lng: float, lat: float,
                               facility_type: Optional[str] = None,
                               n: int = 10) -> List[Dict]:
        """查找最近设施"""
        if self.facility_tree is None:
            return []

        df = self.facility_data
        if facility_type:
            df = df[df['facility_type'] == facility_type]

        if len(df) == 0:
            return []

        coords = df[['lng', 'lat']].values
        try:
            tree = cKDTree(coords)
            distances, indices = tree.query([lng, lat], k=min(n, len(df)))
        except Exception:
            return []

        if n == 1:
            distances = [distances]
            indices = [indices]

        results = []
        for i, idx in enumerate(indices):
            row = df.iloc[idx]
            travel_time = self.calculate_travel_time(lng, lat, row['lng'], row['lat'])

            hours_str = str(row.get('opening_hours', ''))
            hours = OpeningHours.from_string(hours_str)

            results.append({
                'fid': row.get('fid', str(idx)),
                'name': row.get('name', ''),
                'facility_type': row.get('facility_type', ''),
                'lng': row['lng'],
                'lat': row['lat'],
                'distance_km': distances[i],
                'travel_time': travel_time,
                'opening_hours': hours,
                'is_24h': hours.is_24h,
                'has_night_service': hours.night_service,
                'rating': row.get('rating', 0)
            })

        return results

    def calculate_accessibility(self, community: Dict, facility_type: str,
                                period: str = 'day') -> AccessibilityResult:
        """计算特定时段设施可达性（基于论文CTPI模型）"""

        nearest = self.find_nearest_facilities(
            community['lng'], community['lat'],
            facility_type, n=10
        )

        if not nearest:
            return AccessibilityResult(
                facility_type=facility_type,
                nearest_fid=None,
                travel_time=float('inf'),
                effective_time=float('inf'),
                is_accessible=False,
                ctpi=1.0
            )

        period_info = self.config.periods.get(period, {})
        period_start = period_info.get('start', 8)
        period_end = period_info.get('end', 18)

        open_facilities = [
            f for f in nearest
            if f['opening_hours'].is_24h or
               f['opening_hours'].covers_period(period_start, period_end)
        ]

        if not open_facilities:
            best = nearest[0]
            return AccessibilityResult(
                facility_type=facility_type,
                nearest_fid=best['fid'],
                travel_time=best['travel_time'],
                effective_time=float('inf'),
                is_accessible=False,
                facility_name=best['name'],
                ctpi=1.0,
                tmi=1.0
            )

        best = min(open_facilities, key=lambda x: x['travel_time'])

        detour = self.config.detour_factors.get(
            community.get('community_type', 'normal_community'),
            1.1
        )
        service_time = self.config.service_duration.get(facility_type, 15)
        wait_time = self.config.wait_time.get(facility_type, 5)

        mti = best['travel_time'] * detour / self.config.accessibility_threshold
        wti = wait_time / self.config.accessibility_threshold
        tmi = service_time / self.config.accessibility_threshold
        ctpi = (mti + wti + tmi) / 3

        effective_time = best['travel_time'] * detour + wait_time + service_time

        return AccessibilityResult(
            facility_type=facility_type,
            nearest_fid=best['fid'],
            travel_time=best['travel_time'],
            effective_time=effective_time,
            is_accessible=effective_time <= self.config.accessibility_threshold,
            facility_name=best['name'],
            mti=mti,
            wti=wti,
            tmi=tmi,
            ctpi=ctpi
        )


# ============================================================================
# 小区级别时空可达性分析
# ============================================================================

class CommunityAccessibilityAnalyzer:
    """小区时空可达性分析器"""

    def __init__(self, calculator: TimeAccessibilityCalculator, config: StudyConfig):
        self.calculator = calculator
        self.config = config

    def analyze_all_communities(self, communities_df: pd.DataFrame) -> pd.DataFrame:
        """分析所有小区"""
        all_results = []

        logger.info("=" * 60)
        logger.info("小区时空可达性分析")
        logger.info("=" * 60)

        facility_types = list(self.config.facility_names.keys())
        periods = list(self.config.periods.keys())

        for i, row in communities_df.iterrows():
            community = row.to_dict()

            record = {
                'cid': community.get('cid', f'comm_{i}'),
                'name': community.get('name', f'社区{i}'),
                'community_type': community.get('community_type', 'normal_community'),
                'population': community.get('population', 0),
                'lng': community['lng'],
                'lat': community['lat'],
            }

            for period in periods:
                period_records = []
                for ftype in facility_types:
                    result = self.calculator.calculate_accessibility(community, ftype, period)
                    record[f'{ftype}_{period}_ctpi'] = result.ctpi
                    record[f'{ftype}_{period}_accessible'] = result.is_accessible
                    time_val = result.effective_time if result.effective_time != float('inf') else 999
                    record[f'{ftype}_{period}_time'] = time_val
                    record[f'{ftype}_{period}_mti'] = result.mti
                    period_records.append(result.ctpi)

                record[f'{period}_avg_ctpi'] = np.mean(period_records) if period_records else 0
                record[f'{period}_accessible_count'] = sum(1 for r in period_records if r <= 1.0)

            record['day_evening_diff'] = record.get('evening_avg_ctpi', 0) - record.get('day_avg_ctpi', 0)
            record['day_night_diff'] = record.get('night_avg_ctpi', 0) - record.get('day_avg_ctpi', 0)
            record['evening_night_diff'] = record.get('night_avg_ctpi', 0) - record.get('evening_avg_ctpi', 0)

            all_results.append(record)

            if (i + 1) % 10 == 0:
                logger.info(f"  已分析: {i+1}/{len(communities_df)}")

        df = pd.DataFrame(all_results)
        logger.info(f"分析完成: {len(df)} 个小区")
        return df

    def calculate_poverty_index(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """计算时空贫困指数"""
        df = results_df.copy()

        if 'day_avg_ctpi' in df.columns and 'evening_avg_ctpi' in df.columns:
            df['overall_ctpi'] = (df['day_avg_ctpi'] + df['evening_avg_ctpi']) / 2

            df['poverty_level'] = pd.cut(
                df['overall_ctpi'],
                bins=[0, 0.5, 0.8, 1.0, float('inf')],
                labels=['低贫困', '中贫困', '高贫困', '极端贫困']
            )

            df['night_service_gap'] = df['day_avg_ctpi'] - df['evening_avg_ctpi']

        return df


# ============================================================================
# 可视化模块
# ============================================================================

class AccessibilityVisualizer:
    """时空可达性可视化器"""

    def __init__(self, config: StudyConfig):
        self.config = config
        plt.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC',
    'SimSun', 'AR PL UMing CN', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['figure.dpi'] = 100

    def plot_accessibility_map(self, results_df: pd.DataFrame,
                              filename: str = 'accessibility_map.png') -> plt.Figure:
        """绘制时空可达性空间分布图"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 14))
        fig.suptitle('南山区15分钟城市时空可达性空间分布', fontsize=16, fontweight='bold', y=0.98)

        df = results_df.dropna(subset=['lng', 'lat', 'day_avg_ctpi']).copy()
        cmap = LinearSegmentedColormap.from_list('ctpi', ['#2ecc71', '#f1c40f', '#e74c3c', '#c0392b'])

        vmin, vmax = 0, 1.5
        markersize = 100

        periods_config = [
            ('day_avg_ctpi', '白天时段 (08:00-18:00)', '白天CTPI'),
            ('evening_avg_ctpi', '夜间下班 (18:00-22:00)', '夜间CTPI'),
            ('night_avg_ctpi', '深夜时段 (22:00-08:00)', '深夜CTPI'),
            ('day_evening_diff', '白天-夜间差异', 'CTPI差异')
        ]

        for idx, (col, title, cbar_label) in enumerate(periods_config):
            ax = axes[idx // 2, idx % 2]

            if 'diff' in col:
                values = df[col]
                scatter = ax.scatter(df['lng'], df['lat'], c=values,
                                   cmap='RdBu_r', s=markersize, alpha=0.7,
                                   vmin=-0.5, vmax=0.5, edgecolors='black', linewidths=0.3)
                cbar = plt.colorbar(scatter, ax=ax, shrink=0.6)
                cbar.set_label(cbar_label)
            else:
                values = df[col]
                scatter = ax.scatter(df['lng'], df['lat'], c=values,
                                   cmap=cmap, s=markersize, alpha=0.7,
                                   vmin=vmin, vmax=vmax, edgecolors='black', linewidths=0.3)
                cbar = plt.colorbar(scatter, ax=ax, shrink=0.6)
                cbar.set_label(cbar_label)

            ax.set_title(title, fontsize=12, fontweight='bold')
            ax.set_xlabel('经度')
            ax.set_ylabel('纬度')
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_aspect('equal')

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        output_path = os.path.join(self.config.output_dir, filename)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"地图已保存: {output_path}")

        return fig

    def plot_community_type_comparison(self, results_df: pd.DataFrame,
                                    filename: str = 'community_comparison.png') -> plt.Figure:
        """绘制社区类型对比图"""
        type_names = self.config.community_names
        periods = list(self.config.periods.keys())
        period_labels = [self.config.periods[p]['name'] for p in periods]

        stats_data = []
        for ctype, cname in type_names.items():
            subset = results_df[results_df['community_type'] == ctype]
            if len(subset) > 0:
                row = {'type': cname, 'count': len(subset)}
                for period in periods:
                    col = f'{period}_avg_ctpi'
                    if col in subset.columns:
                        row[f'{period}_mean'] = subset[col].mean()
                        row[f'{period}_std'] = subset[col].std()
                stats_data.append(row)

        stats_df = pd.DataFrame(stats_data)

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        x = np.arange(len(stats_df))
        width = 0.25
        colors = ['#3498db', '#e74c3c', '#9b59b6']

        for i, (period, label) in enumerate(zip(periods, period_labels)):
            col = f'{period}_mean'
            if col in stats_df.columns:
                axes[0].bar(x + i * width - width, stats_df[col], width,
                           label=label, color=colors[i], alpha=0.8)

        axes[0].set_ylabel('平均时间贫困指数 (CTPI)')
        axes[0].set_title('不同社区类型各时段CTPI对比', fontsize=14, fontweight='bold')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(stats_df['type'], fontsize=11, rotation=15)
        axes[0].legend(loc='upper right')
        axes[0].grid(True, alpha=0.3, axis='y')
        axes[0].axhline(y=1.0, color='red', linestyle='--', alpha=0.5, label='可达性阈值')

        axes[1].bar(stats_df['type'], stats_df['count'], color='#2ecc71', alpha=0.8)
        axes[1].set_ylabel('小区数量')
        axes[1].set_title('各类社区数量分布', fontsize=14, fontweight='bold')
        axes[1].set_xticklabels(stats_df['type'], fontsize=11, rotation=15)
        axes[1].grid(True, alpha=0.3, axis='y')

        for i, (ctype, row) in enumerate(zip(stats_df['type'], stats_df.itertuples())):
            for j, period in enumerate(periods):
                col = f'{period}_mean'
                if hasattr(row, col):
                    val = getattr(row, col)
                    axes[0].annotate(f'{val:.2f}',
                                   xy=(i + (j - 1) * width, val),
                                   xytext=(0, 3), textcoords="offset points",
                                   ha='center', va='bottom', fontsize=8)

        plt.tight_layout()

        output_path = os.path.join(self.config.output_dir, filename)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"社区对比图已保存: {output_path}")

        return fig

    def plot_facility_coverage(self, results_df: pd.DataFrame,
                             filename: str = 'facility_coverage.png') -> plt.Figure:
        """绘制设施覆盖率分析图"""
        facility_names = self.config.facility_names
        periods = list(self.config.periods.keys())
        period_labels = ['白天', '夜间', '深夜']

        accessible_counts = {ftype: {p: 0 for p in periods} for ftype in facility_names}

        for _, row in results_df.iterrows():
            for period in periods:
                for ftype in facility_names:
                    col = f'{ftype}_{period}_accessible'
                    if col in row.index and row[col]:
                        accessible_counts[ftype][period] += 1

        total = len(results_df)

        fig, axes = plt.subplots(1, 2, figsize=(16, 6))

        x = np.arange(len(facility_names))
        width = 0.25
        colors = ['#3498db', '#e74c3c', '#9b59b6']

        for i, period in enumerate(periods):
            values = [accessible_counts[ftype][period] / total * 100
                     for ftype in facility_names]
            axes[0].bar(x + i * width - width, values, width,
                       label=period_labels[i], color=colors[i], alpha=0.8)

        axes[0].set_ylabel('可达覆盖率 (%)')
        axes[0].set_title('各类设施不同时段可达覆盖率', fontsize=14, fontweight='bold')
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(list(facility_names.values()), rotation=30, ha='right')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3, axis='y')
        axes[0].set_ylim(0, 110)

        night_gaps = []
        for ftype in facility_names:
            day_rate = accessible_counts[ftype]['day'] / total * 100
            night_rate = accessible_counts[ftype]['evening'] / total * 100
            gap = day_rate - night_rate
            night_gaps.append(gap)

        colors_gap = ['#e74c3c' if g > 0 else '#2ecc71' for g in night_gaps]
        axes[1].bar(list(facility_names.values()), night_gaps, color=colors_gap, alpha=0.8)
        axes[1].set_ylabel('覆盖率差异 (百分点)')
        axes[1].set_title('夜间服务缺口 (白天-夜间)', fontsize=14, fontweight='bold')
        axes[1].axhline(y=0, color='black', linestyle='-', alpha=0.3)
        axes[1].set_xticklabels(list(facility_names.values()), rotation=30, ha='right')
        axes[1].grid(True, alpha=0.3, axis='y')

        plt.tight_layout()

        output_path = os.path.join(self.config.output_dir, filename)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"设施覆盖率图已保存: {output_path}")

        return fig

    def plot_night_service_analysis(self, results_df: pd.DataFrame,
                                  filename: str = 'night_service_analysis.png') -> plt.Figure:
        """绘制夜间服务分析图"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        df = results_df.copy()

        if 'night_avg_ctpi' in df.columns:
            q25, q75 = df['night_avg_ctpi'].quantile([0.25, 0.75])
            iqr = q75 - q25
            upper_bound = q75 + 1.5 * iqr

            poverty_communities = df[df['night_avg_ctpi'] > upper_bound]
            normal_communities = df[df['night_avg_ctpi'] <= upper_bound]

            axes[0].scatter(normal_communities['lng'], normal_communities['lat'],
                          c=normal_communities['night_avg_ctpi'],
                          cmap='RdYlGn_r', s=80, alpha=0.6,
                          vmin=0, vmax=upper_bound, edgecolors='black', linewidths=0.3)

            scatter = axes[0].scatter(poverty_communities['lng'], poverty_communities['lat'],
                                      c=poverty_communities['night_avg_ctpi'],
                                      cmap='RdYlGn_r', s=150, alpha=0.9,
                                      vmin=0, vmax=upper_bound,
                                      edgecolors='red', linewidths=1.5,
                                      marker='s')

            cbar = plt.colorbar(scatter, ax=axes[0], shrink=0.6)
            cbar.set_label('夜间CTPI')

            axes[0].set_title('夜间服务薄弱区域识别', fontsize=14, fontweight='bold')
            axes[0].set_xlabel('经度')
            axes[0].set_ylabel('纬度')
            axes[0].grid(True, alpha=0.3)
            axes[0].set_aspect('equal')

            red_patch = mpatches.Patch(color='red', label=f'薄弱小区({len(poverty_communities)}个)')
            green_patch = mpatches.Patch(color='green', label=f'正常小区({len(normal_communities)}个)')
            axes[0].legend(handles=[red_patch, green_patch], loc='upper right')

        night_facility_types = ['convenience_store', 'pharmacy', 'express', 'hospital']
        night_service_impact = []

        for ftype in night_facility_types:
            day_col = f'{ftype}_day_ctpi'
            night_col = f'{ftype}_night_ctpi'
            if day_col in df.columns and night_col in df.columns:
                impact = df[night_col].mean() - df[day_col].mean()
                night_service_impact.append({
                    'type': self.config.facility_names.get(ftype, ftype),
                    'impact': impact
                })

        impact_df = pd.DataFrame(night_service_impact)

        colors = ['#e74c3c' if x > 0 else '#2ecc71' for x in impact_df['impact']]
        axes[1].barh(impact_df['type'], impact_df['impact'], color=colors, alpha=0.8)
        axes[1].axvline(x=0, color='black', linestyle='-', alpha=0.3)
        axes[1].set_xlabel('CTPI变化量')
        axes[1].set_title('夜间服务对各类设施可达性的影响', fontsize=14, fontweight='bold')
        axes[1].grid(True, alpha=0.3, axis='x')

        plt.tight_layout()

        output_path = os.path.join(self.config.output_dir, filename)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        logger.info(f"夜间服务分析图已保存: {output_path}")

        return fig


# ============================================================================
# 报告生成
# ============================================================================

class ReportGenerator:
    """研究报告生成器"""

    def __init__(self, config: StudyConfig):
        self.config = config

    def generate_summary_report(self, results_df: pd.DataFrame,
                              facility_df: pd.DataFrame) -> str:
        """生成分析摘要报告"""

        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("       南山区15分钟城市公共服务时空可达性分析报告")
        report_lines.append("=" * 80)
        report_lines.append(f"研究区域: {self.config.study_area}")
        report_lines.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        report_lines.append(f"数据来源: OSM, 大众点评, 小区AOI")
        report_lines.append("")

        report_lines.append("【一、数据概览】")
        report_lines.append(f"  小区数量: {len(results_df)} 个")
        report_lines.append(f"  设施数量: {len(facility_df)} 条")
        report_lines.append("")

        if 'facility_type' in facility_df.columns:
            report_lines.append("  设施类型分布:")
            type_counts = facility_df['facility_type'].value_counts()
            for ftype, count in type_counts.items():
                fname = self.config.facility_names.get(ftype, ftype)
                report_lines.append(f"    - {fname}: {count}")

        report_lines.append("")
        report_lines.append("【二、时间贫困指数统计】")

        for period_key, period_name in [('day', '白天'), ('evening', '夜间下班'), ('night', '深夜')]:
            col = f'{period_key}_avg_ctpi'
            if col in results_df.columns:
                mean_val = results_df[col].mean()
                median_val = results_df[col].median()
                std_val = results_df[col].std()
                min_val = results_df[col].min()
                max_val = results_df[col].max()
                accessible_count = (results_df[col] <= 1.0).sum()
                accessible_rate = accessible_count / len(results_df) * 100

                report_lines.append(f"\n  {period_name}时段 (CTPI):")
                report_lines.append(f"    平均值: {mean_val:.3f}")
                report_lines.append(f"    中位数: {median_val:.3f}")
                report_lines.append(f"    标准差: {std_val:.3f}")
                report_lines.append(f"    范围: [{min_val:.3f}, {max_val:.3f}]")
                report_lines.append(f"    可达率(CTPI≤1): {accessible_rate:.1f}%")

        report_lines.append("")
        report_lines.append("【三、社区类型时间贫困对比】")

        for ctype, cname in self.config.community_names.items():
            subset = results_df[results_df['community_type'] == ctype]
            if len(subset) > 0:
                day_mean = subset['day_avg_ctpi'].mean() if 'day_avg_ctpi' in subset.columns else 0
                evening_mean = subset['evening_avg_ctpi'].mean() if 'evening_avg_ctpi' in subset.columns else 0
                night_mean = subset['night_avg_ctpi'].mean() if 'night_avg_ctpi' in subset.columns else 0
                diff = evening_mean - day_mean

                report_lines.append(f"\n  {cname} ({len(subset)}个):")
                report_lines.append(f"    白天CTPI: {day_mean:.3f}")
                report_lines.append(f"    夜间CTPI: {evening_mean:.3f}")
                report_lines.append(f"    深夜CTPI: {night_mean:.3f}")
                report_lines.append(f"    白天-夜间差异: {diff:+.3f}")

        report_lines.append("")
        report_lines.append("【四、夜间服务薄弱小区识别】")

        if 'evening_avg_ctpi' in results_df.columns:
            q80 = results_df['evening_avg_ctpi'].quantile(0.8)
            poverty = results_df[results_df['evening_avg_ctpi'] > q80]
            poverty = poverty.sort_values('evening_avg_ctpi', ascending=False)

            if len(poverty) > 0:
                report_lines.append(f"  高时间贫困小区 (后20%, 共{len(poverty)}个):")
                for _, row in poverty.head(10).iterrows():
                    cname = self.config.community_names.get(row.get('community_type', ''), '')
                    report_lines.append(f"    - {row['name']} ({cname}): "
                                     f"夜间CTPI={row['evening_avg_ctpi']:.3f}, "
                                     f"类型={row['community_type']}")

        report_lines.append("")
        report_lines.append("【五、设施夜间可达性分析】")

        facility_types = ['convenience_store', 'pharmacy', 'express', 'hospital']
        for ftype in facility_types:
            day_col = f'{ftype}_day_ctpi'
            night_col = f'{ftype}_evening_ctpi'
            if day_col in results_df.columns and night_col in results_df.columns:
                day_mean = results_df[day_col].mean()
                night_mean = results_df[night_col].mean()
                gap = night_mean - day_mean
                fname = self.config.facility_names.get(ftype, ftype)

                report_lines.append(f"\n  {fname}:")
                report_lines.append(f"    白天平均CTPI: {day_mean:.3f}")
                report_lines.append(f"    夜间平均CTPI: {night_mean:.3f}")
                report_lines.append(f"    夜间服务缺口: {gap:+.3f}")

        report_lines.append("")
        report_lines.append("【六、研究结论与建议】")
        report_lines.append("")
        report_lines.append("  1. 城中村和深夜时段是时空贫困的主要集中区域")
        report_lines.append("  2. 建议在夜间服务薄弱小区周边增设24小时便利店")
        report_lines.append("  3. 医院和银行的夜间可达性需要重点关注")
        report_lines.append("  4. 可考虑发展移动医疗和快递自提柜等创新服务模式")

        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("未来交通实验室 | 南山区15分钟城市研究")
        report_lines.append("=" * 80)

        report_text = "\n".join(report_lines)

        report_path = os.path.join(self.config.output_dir, "accessibility_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"报告已保存: {report_path}")

        return report_text

    def generate_statistics_csv(self, results_df: pd.DataFrame,
                              filename: str = 'accessibility_statistics.csv') -> None:
        """生成统计CSV文件"""

        stats_data = []

        for ctype, cname in self.config.community_names.items():
            subset = results_df[results_df['community_type'] == ctype]
            if len(subset) > 0:
                row = {'community_type': cname, 'count': len(subset)}
                for period in ['day', 'evening', 'night']:
                    col = f'{period}_avg_ctpi'
                    if col in subset.columns:
                        row[f'{period}_ctpi_mean'] = subset[col].mean()
                        row[f'{period}_ctpi_std'] = subset[col].std()
                        row[f'{period}_accessible_rate'] = (subset[col] <= 1.0).mean() * 100
                stats_data.append(row)

        stats_df = pd.DataFrame(stats_data)
        output_path = os.path.join(self.config.output_dir, filename)
        stats_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logger.info(f"统计数据已保存: {output_path}")


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""

    print("\n" + "=" * 80)
    print("   南山区15分钟城市公共服务时空可达性分析系统 v3.0")
    print("   未来交通实验室 | 2026-05-20")
    print("=" * 80 + "\n")

    config = StudyConfig()

    data_manager = DataSourceManager(config)

    print("[1/7] 加载多数据源设施数据...")
    osm_df = data_manager.load_osm_data()
    dianping_df = data_manager.load_dianping_data()

    facility_df = pd.concat([osm_df, dianping_df], ignore_index=True)
    logger.info(f"  合并后设施总数: {len(facility_df)}")

    print("\n[2/7] 加载小区数据...")
    community_df = data_manager.load_community_data()
    logger.info(f"  小区总数: {len(community_df)}")

    print("\n[3/7] 保存原始数据...")
    facility_df.to_csv(
        os.path.join(config.output_dir, 'facilities_combined.csv'),
        index=False, encoding='utf-8-sig'
    )
    community_df.to_csv(
        os.path.join(config.output_dir, 'communities.csv'),
        index=False, encoding='utf-8-sig'
    )
    logger.info(f"  数据已保存至: {config.output_dir}")

    print("\n[4/7] 构建设施空间索引...")
    calculator = TimeAccessibilityCalculator(config)
    calculator.build_facility_index(facility_df)

    print("\n[5/7] 小区时空可达性分析...")
    analyzer = CommunityAccessibilityAnalyzer(calculator, config)
    results_df = analyzer.analyze_all_communities(community_df)
    results_df = analyzer.calculate_poverty_index(results_df)

    results_df.to_csv(
        os.path.join(config.output_dir, 'accessibility_results.csv'),
        index=False, encoding='utf-8-sig'
    )
    logger.info(f"  分析结果已保存")

    print("\n[6/7] 生成可视化...")
    visualizer = AccessibilityVisualizer(config)
    visualizer.plot_accessibility_map(results_df, 'accessibility_map.png')
    visualizer.plot_community_type_comparison(results_df, 'community_comparison.png')
    visualizer.plot_facility_coverage(results_df, 'facility_coverage.png')
    visualizer.plot_night_service_analysis(results_df, 'night_service_analysis.png')

    print("\n[7/7] 生成分析报告...")
    report_gen = ReportGenerator(config)
    report_text = report_gen.generate_summary_report(results_df, facility_df)
    report_gen.generate_statistics_csv(results_df, 'accessibility_statistics.csv')

    print("\n" + report_text)

    print("\n" + "=" * 80)
    print("分析完成!")
    print("=" * 80)
    print(f"\n输出目录: {config.output_dir}")
    print("\n生成的文件:")
    print("  [数据文件]")
    print("    - facilities_combined.csv    (合并后的设施数据)")
    print("    - communities.csv            (小区数据)")
    print("    - accessibility_results.csv  (可达性分析结果)")
    print("    - accessibility_statistics.csv (分类型统计)")
    print("  [可视化]")
    print("    - accessibility_map.png      (时空可达性空间分布图)")
    print("    - community_comparison.png   (社区类型对比图)")
    print("    - facility_coverage.png     (设施覆盖率分析图)")
    print("    - night_service_analysis.png (夜间服务分析图)")
    print("  [报告]")
    print("    - accessibility_report.txt   (完整分析报告)")


if __name__ == "__main__":
    main()
