# -*- coding: utf-8 -*-
"""
15分钟城市时间贫困研究 - 核心代码框架
=====================================

此脚本提供研究的完整技术实现框架：
1. 数据加载与预处理
2. 坐标系统一转换
3. 网络分析
4. 时间可达性计算
5. 时间贫困指数构建
6. 可视化

使用说明：
1. 需先安装: pip install geopandas osmnx contextily
2. POI数据需从Access数据库导出为CSV
3. 运行前配置好数据路径
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = [
    'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'Noto Sans SC',
    'SimSun', 'AR PL UMing CN', 'WenQuanYi Micro Hei', 'Arial Unicode MS', 'DejaVu Sans'
]
matplotlib.rcParams['axes.unicode_minus'] = False

import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# 第一部分：配置与常量
# ============================================================================

class Config:
    """全局配置"""
    
    # 数据路径
    BASE_DIR = r"E:\xicha gis 智能定位"
    ROAD_SHP = f"{BASE_DIR}\\GData1\\nsPT.shp"
    BUILDING_SHP = f"{BASE_DIR}\\气候图基础数据\\pdbuilding.shp"
    LANDUSE_SHP = f"{BASE_DIR}\\气候图基础数据\\pdlanduse.shp"
    BOUNDARY_SHP = f"{BASE_DIR}\\GData2\\区级边界New.shp"
    POI_CSV = f"{BASE_DIR}\\GData1\\poi_data.csv"  # 需从Access导出
    ACCESS_DB = f"{BASE_DIR}\\GData1\\test.mdb"
    
    # 坐标系
    SRC_CRS = "EPSG:32649"  # WGS 1984 UTM Zone 49N
    DST_CRS = "EPSG:4527"   # CGCS2000 3度带，中央经线114°E
    
    # 时间参数（分钟）
    WALK_SPEED_KMH = 5.0  # 步行速度 km/h
    AVAILABLE_TIME = 120    # 单次出行可支配时间（分钟）
    
    # 时段定义
    PERIODS = {
        'day': {'start': 8, 'end': 18, 'name': '白天'},
        'evening': {'start': 18, 'end': 22, 'name': '夜间下班'},
        'night': {'start': 22, 'end': 8, 'name': '深夜应急'}
    }
    
    # 曲折系数（按社区类型）
    DETOUR_FACTORS = {
        'urban_village': 1.5,    # 城中村
        'old_community': 1.3,      # 老旧小区
        'normal_community': 1.1, # 普通商品房
        'high_end': 1.0          # 高端社区
    }
    
    # 标准办理时间（分钟）
    SERVICE_DURATION = {
        'convenience_store': 5,    # 便利店
        'pharmacy': 10,           # 药店
        'supermarket': 15,        # 超市
        'hospital': 30,          # 医院
        'bank': 45,               # 银行
        'express': 8,             # 快递
        'market': 15,             # 菜市场
        'community_center': 20     # 社区服务中心
    }


# ============================================================================
# 第二部分：数据加载与预处理
# ============================================================================

class DataLoader:
    """数据加载器"""
    
    @staticmethod
    def load_poi_from_access(db_path, export_csv=None):
        """
        从Access数据库加载POI数据
        
        参数:
            db_path: Access数据库路径
            export_csv: 可选，导出为CSV的路径
        
        返回:
            DataFrame: POI数据
        
        注意: Windows下需使用Access应用程序打开并导出
        """
        print("⚠️ Access数据库读取需要以下方式之一:")
        print("   1. 使用Access应用程序打开，导出为CSV")
        print("   2. 使用ArcGIS/QGIS打开，导出为CSV/Shapefile")
        print("   3. 在64位Windows上安装Access Runtime")
        
        # 示例代码（Access导出后的CSV读取）
        if export_csv and os.path.exists(export_csv):
            df = pd.read_csv(export_csv, encoding='utf-8')
            print(f"✅ 从CSV加载POI数据: {len(df)} 条记录")
            return df
        
        return None
    
    @staticmethod
    def load_poi_from_csv(csv_path):
        """从CSV加载POI数据"""
        if not os.path.exists(csv_path):
            print(f"❌ 文件不存在: {csv_path}")
            return None
        
        df = pd.read_csv(csv_path, encoding='utf-8')
        print(f"✅ 加载POI数据: {len(df):,} 条记录")
        print(f"   字段: {df.columns.tolist()}")
        return df
    
    @staticmethod
    def load_road_network(shp_path):
        """
        加载道路网络数据
        
        返回:
            GeoDataFrame: 道路数据
        """
        try:
            import geopandas as gpd
            gdf = gpd.read_file(shp_path)
            print(f"✅ 加载道路网络: {len(gdf):,} 条记录")
            return gdf
        except ImportError:
            print("❌ 需要安装geopandas: pip install geopandas")
            return None
    
    @staticmethod
    def load_buildings(shp_path):
        """加载建筑数据"""
        try:
            import geopandas as gpd
            gdf = gpd.read_file(shp_path)
            print(f"✅ 加载建筑数据: {len(gdf):,} 条记录")
            return gdf
        except ImportError:
            print("❌ 需要安装geopandas")
            return None


# ============================================================================
# 第三部分：坐标系统一
# ============================================================================

class CoordinateTransformer:
    """坐标转换工具"""
    
    def __init__(self, src_crs, dst_crs):
        self.src_crs = src_crs
        self.dst_crs = dst_crs
        self.transformer = None
        
        try:
            from pyproj import Transformer
            self.transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
            print(f"✅ 坐标系转换器已创建: {src_crs} → {dst_crs}")
        except ImportError:
            print("❌ 需要安装pyproj: pip install pyproj")
        except Exception as e:
            print(f"⚠️ 转换器创建失败: {e}")
    
    def transform_point(self, x, y):
        """转换单个点坐标"""
        if self.transformer is None:
            return x, y
        return self.transformer.transform(x, y)
    
    def transform_df(self, df, x_col, y_col, new_x_col='x_cgcs', new_y_col='y_cgcs'):
        """转换DataFrame中的坐标"""
        if self.transformer is None:
            return df
        
        df[new_x_col], df[new_y_col] = self.transformer.transform(
            df[x_col].values, 
            df[y_col].values
        )
        print(f"✅ 已转换 {len(df):,} 个点的坐标")
        return df
    
    @staticmethod
    def gcj02_to_wgs84(lng, lat):
        """
        GCJ-02（火星坐标系）转WGS84
        用于处理来自高德/腾讯地图的POI数据
        """
        import math
        
        a = 6378245.0  # 长半轴
        ee = 0.00669342162296594323  # 扁率
        
        def transform(lng, lat):
            dlat = CoordinateTransformer._transform_lat(lng - 105.0, lat - 35.0)
            dlng = CoordinateTransformer._transform_lng(lng - 105.0, lat - 35.0)
            radlat = lat / 180.0 * math.pi
            magic = math.sin(radlat)
            magic = 1 - ee * magic * magic
            sqrtmagic = math.sqrt(magic)
            dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
            dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
            return lng - dlng, lat - dlat
        
        return transform(lng, lat)
    
    @staticmethod
    def _transform_lat(x, y):
        import math
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
        ret += 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y / 30.0 * math.pi)) * 2.0 / 3.0
        return ret
    
    @staticmethod
    def _transform_lng(x, y):
        import math
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret


# ============================================================================
# 第四部分：设施分类与时间解析
# ============================================================================

class FacilityClassifier:
    """设施分类器"""
    
    # POI类型映射表（高德地图分类）
    AMAP_CATEGORIES = {
        # 餐饮购物
        '便利店': ('retail', 'convenience_store', True),
        '超市': ('retail', 'supermarket', False),
        '药店': ('medical', 'pharmacy', True),
        '商场': ('retail', 'mall', False),
        '便利店': ('retail', 'convenience_store', True),
        
        # 医疗健康
        '医院': ('medical', 'hospital', True),
        '诊所': ('medical', 'clinic', False),
        '社区卫生服务中心': ('medical', 'community_health', True),
        
        # 金融
        '银行': ('financial', 'bank', False),
        'ATM': ('financial', 'atm', True),
        
        # 生活服务
        '快递': ('logistics', 'express', True),
        '菜市场': ('retail', 'market', False),
        '社区服务中心': ('government', 'community_center', False),
        
        # 教育
        '学校': ('education', 'school', False),
        '幼儿园': ('education', 'kindergarten', False),
    }
    
    @staticmethod
    def parse_opening_hours(hours_str):
        """
        解析营业时间字符串
        
        参数:
            hours_str: 营业时间字符串，如 "08:00-22:00"
        
        返回:
            dict: 解析后的时间信息
        """
        if pd.isna(hours_str) or not hours_str:
            return {'24h': False, 'open_all_day': False, 'day_hours': None}
        
        hours_str = str(hours_str).strip()
        
        # 24小时
        if '24' in hours_str or '24小时' in hours_str:
            return {'24h': True, 'open_all_day': True, 'day_hours': (0, 24)}
        
        # 尝试解析 "08:00-22:00" 格式
        try:
            if '-' in hours_str:
                parts = hours_str.split('-')
                start = parts[0].strip()
                end = parts[1].strip()
                
                # 解析小时
                start_h = int(start.split(':')[0]) if ':' in start else int(start)
                end_h = int(end.split(':')[0]) if ':' in end else int(end)
                
                return {'24h': False, 'open_all_day': False, 'day_hours': (start_h, end_h)}
        except:
            pass
        
        return {'24h': False, 'open_all_day': False, 'day_hours': None}
    
    @staticmethod
    def is_open_at(period_info, period_name):
        """
        判断设施在特定时段是否开放
        
        参数:
            period_info: parse_opening_hours返回的信息
            period_name: 时段名称 ('day', 'evening', 'night')
        
        返回:
            bool: 是否开放
        """
        if period_info.get('24h', False):
            return True
        
        if period_info.get('open_all_day', False):
            return True
        
        day_hours = period_info.get('day_hours')
        if day_hours is None:
            return False
        
        start_h, end_h = day_hours
        
        period = Config.PERIODS.get(period_name, {})
        period_start = period.get('start', 0)
        period_end = period.get('end', 24)
        
        # 处理跨天情况
        if period_start >= period_end:  # 夜间时段如22:00-08:00
            # 检查时段起始部分
            if start_h >= period_start and end_h <= 24:
                return True
            if start_h >= 0 and end_h <= period_end:
                return True
        else:
            # 正常白天时段
            if start_h <= period_start and end_h >= period_end:
                return True
            if start_h >= period_start and end_h <= period_end:
                return True
        
        return False
    
    @staticmethod
    def classify_poi(poi_type):
        """分类POI设施类型"""
        return FacilityClassifier.AMAP_CATEGORIES.get(poi_type, ('other', 'other', False))


# ============================================================================
# 第五部分：网络分析
# ============================================================================

class NetworkAnalyzer:
    """网络分析工具"""
    
    def __init__(self):
        self.G = None
        self.graph_ready = False
    
    def build_network_from_shp(self, road_gdf, boundary_gdf):
        """
        从shapefile构建道路网络图
        
        参数:
            road_gdf: 道路GeoDataFrame
            boundary_gdf: 边界GeoDataFrame
        
        返回:
            NetworkX图对象
        """
        try:
            import osmnx as ox
            import geopandas as gpd
            
            # 方法1：使用OSMNX从边界创建
            boundary = boundary_gdf.unary_union
            G = ox.graph_from_polygon(
                boundary, 
                network_type='walk',
                simplify=True,
                retain_all=False
            )
            
            # 添加速度属性
            G = ox.add_edge_lengths(G)
            
            self.G = G
            self.graph_ready = True
            print(f"✅ 道路网络构建完成: {len(G.nodes)} 节点, {len(G.edges)} 边")
            
            return G
            
        except ImportError:
            print("❌ 需要安装osmnx: pip install osmnx")
            return None
        except Exception as e:
            print(f"❌ 网络构建失败: {e}")
            return None
    
    def calculate_travel_time(self, origin, destination):
        """
        计算两点间最短路径时间（分钟）
        
        参数:
            origin: (lng, lat) 起点
            destination: (lng, lat) 终点
        
        返回:
            float: 最短路径时间（分钟）
        """
        if not self.graph_ready:
            return None
        
        try:
            import networkx as nx
            
            # 转换为网络节点
            origin_node = ox.distance.nearest_nodes(self.G, origin[0], origin[1])
            dest_node = ox.distance.nearest_nodes(self.G, destination[0], destination[1])
            
            # 计算最短路径长度
            length = nx.shortest_path_length(
                self.G, 
                origin_node, 
                dest_node, 
                weight='length'
            )
            
            # 转换为时间（分钟）
            speed_m_per_min = Config.WALK_SPEED_KMH * 1000 / 60
            time_min = length / speed_m_per_min
            
            return time_min
            
        except Exception as e:
            return None
    
    def calculate_detour_factor(self, origin_node, destination_node):
        """
        计算曲折系数
        
        基于出发地和目的地的社区类型
        """
        # 简化版：使用固定系数
        # 完整版需结合建筑数据分析
        return 1.0


# ============================================================================
# 第六部分：时间可达性计算
# ============================================================================

class TimeAccessibilityCalculator:
    """时间可达性计算器"""
    
    def __init__(self, network_analyzer):
        self.analyzer = network_analyzer
    
    def calculate_effective_time(self, community, poi, period='day'):
        """
        计算有效服务时间
        
        公式: T_effective = T_travel × F_detour + T_wait + T_service
        
        参数:
            community: 社区信息（包含坐标和类型）
            poi: 设施信息（包含坐标、类型、开放时间）
            period: 时段 ('day', 'evening', 'night')
        
        返回:
            dict: 计算结果
        """
        # 1. 检查设施在该时段是否开放
        period_info = FacilityClassifier.parse_opening_hours(poi.get('opening_hours', ''))
        
        if not FacilityClassifier.is_open_at(period_info, period):
            return {
                'available': False,
                'reason': 'facility_closed',
                'effective_time': float('inf')
            }
        
        # 2. 计算移动时间
        origin = (community['lng'], community['lat'])
        destination = (poi['lng'], poi['lat'])
        
        travel_time = self.analyzer.calculate_travel_time(origin, destination)
        
        if travel_time is None:
            return {
                'available': False,
                'reason': 'no_route',
                'effective_time': float('inf')
            }
        
        # 3. 计算曲折系数
        community_type = community.get('type', 'normal_community')
        detour_factor = Config.DETOUR_FACTORS.get(community_type, 1.0)
        
        # 4. 计算等待时间（简化版）
        poi_type = poi.get('type', 'other')
        wait_time = self._estimate_wait_time(poi_type)
        
        # 5. 获取办理时间
        service_duration = Config.SERVICE_DURATION.get(poi_type, 15)
        
        # 6. 计算总有效服务时间
        effective_time = travel_time * detour_factor + wait_time + service_duration
        
        return {
            'available': True,
            'travel_time': travel_time,
            'detour_factor': detour_factor,
            'wait_time': wait_time,
            'service_time': service_duration,
            'effective_time': effective_time
        }
    
    def _estimate_wait_time(self, poi_type):
        """
        估算等待时间
        简化版：基于设施类型的平均值
        """
        wait_times = {
            'convenience_store': 2,
            'pharmacy': 10,
            'supermarket': 15,
            'hospital': 25,
            'bank': 20,
            'express': 5,
            'market': 10,
            'community_center': 15
        }
        return wait_times.get(poi_type, 10)
    
    def find_nearest_facility(self, community, poi_df, period='day', facility_type=None):
        """
        找到最近的可达设施
        
        参数:
            community: 社区信息
            poi_df: POI数据DataFrame
            period: 时段
            facility_type: 设施类型过滤
        
        返回:
            dict: 最近设施及其有效服务时间
        """
        if facility_type:
            poi_df = poi_df[poi_df['type'] == facility_type]
        
        results = []
        
        for _, poi in poi_df.iterrows():
            result = self.calculate_effective_time(community, poi.to_dict(), period)
            if result['available']:
                results.append({
                    'poi': poi.to_dict(),
                    **result
                })
        
        if not results:
            return None
        
        # 返回时间最短的设施
        return min(results, key=lambda x: x['effective_time'])


# ============================================================================
# 第七部分：时间贫困指数
# ============================================================================

class TimePovertyIndex:
    """时间贫困指数计算"""
    
    def __init__(self, calculator):
        self.calculator = calculator
    
    def calculate_mti(self, travel_time, threshold=15):
        """
        计算移动时间指数 (MTI)
        MTI = travel_time / threshold
        """
        return travel_time / threshold
    
    def calculate_wti(self, wait_time, threshold=15):
        """
        计算等待时间指数 (WTI)
        WTI = wait_time / threshold
        """
        return wait_time / threshold
    
    def calculate_tmi(self, time_overlap_ratio):
        """
        计算时间窗口匹配指数 (TMI)
        TMI = 1 - overlap_ratio
        """
        return 1 - time_overlap_ratio
    
    def calculate_ctpi(self, mti, wti, tmi, weights=None):
        """
        计算综合时间贫困指数 (CTPI)
        
        公式: CTPI = w1 × MTI + w2 × WTI + w3 × TMI
        
        参数:
            mti: 移动时间指数
            wti: 等待时间指数
            tmi: 时间窗口匹配指数
            weights: 权重 [w1, w2, w3]，默认为等权重 [1/3, 1/3, 1/3]
        
        返回:
            float: 综合时间贫困指数
        """
        if weights is None:
            weights = [1/3, 1/3, 1/3]
        
        return weights[0] * mti + weights[1] * wti + weights[2] * tmi
    
    def calculate_community_ctpi(self, community, poi_df, period='day'):
        """
        计算社区的综合时间贫困指数
        
        参数:
            community: 社区信息
            poi_df: POI数据
            period: 时段
        
        返回:
            dict: 各设施类型的CTPI
        """
        facility_types = ['convenience_store', 'pharmacy', 'supermarket', 'hospital', 'bank']
        results = {}
        
        for ftype in facility_types:
            nearest = self.calculator.find_nearest_facility(
                community, poi_df, period, ftype
            )
            
            if nearest is None:
                results[ftype] = {'ctpi': float('inf'), 'reason': 'no_facility'}
                continue
            
            mti = self.calculate_mti(nearest['travel_time'])
            wti = self.calculate_wti(nearest['wait_time'])
            tmi = self.calculate_tmi(1.0)  # 假设开放时间完全匹配
            
            ctpi = self.calculate_ctpi(mti, wti, tmi)
            
            results[ftype] = {
                'ctpi': ctpi,
                'nearest': nearest,
                'mti': mti,
                'wti': wti,
                'tmi': tmi
            }
        
        return results


# ============================================================================
# 第八部分：可视化
# ============================================================================

class Visualizer:
    """可视化工具"""
    
    @staticmethod
    def plot_time_poverty_map(community_df, title="时间贫困指数分布"):
        """
        绘制时间贫困指数空间分布图
        """
        fig, ax = plt.subplots(1, 1, figsize=(12, 10))
        
        # 绘制底图（如果有）
        try:
            import contextily as ctx
            has_basemap = True
        except:
            has_basemap = False
        
        # 绘制散点
        scatter = ax.scatter(
            community_df['lng'],
            community_df['lat'],
            c=community_df['ctpi'],
            cmap='RdYlGn_r',
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidths=0.5
        )
        
        # 添加颜色条
        cbar = plt.colorbar(scatter, ax=ax, shrink=0.7)
        cbar.set_label('时间贫困指数 (CTPI)', fontsize=12)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('经度')
        ax.set_ylabel('纬度')
        
        # 添加网格
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig, ax
    
    @staticmethod
    def plot_comparison_maps(traditional_map, effective_time_map, difference_map):
        """
        绘制传统vs有效服务时间对比图
        """
        fig, axes = plt.subplots(1, 3, figsize=(18, 6))
        
        # 子图1：传统15分钟步行圈
        im1 = axes[0].imshow(traditional_map, cmap='RdYlGn')
        axes[0].set_title('传统15分钟步行圈', fontsize=12)
        plt.colorbar(im1, ax=axes[0])
        
        # 子图2：有效服务时间
        im2 = axes[1].imshow(effective_time_map, cmap='RdYlGn_r')
        axes[1].set_title('有效服务时间（分钟）', fontsize=12)
        plt.colorbar(im2, ax=axes[1])
        
        # 子图3：差异图
        im3 = axes[2].imshow(difference_map, cmap='RdBu')
        axes[2].set_title('差异（幻觉区域）', fontsize=12)
        plt.colorbar(im3, ax=axes[2])
        
        plt.tight_layout()
        return fig, axes
    
    @staticmethod
    def plot_day_night_comparison(day_ctpi, night_ctpi, communities):
        """
        绘制白天vs夜间时间贫困对比图
        """
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        
        # 白天
        axes[0].scatter(
            communities['lng'],
            communities['lat'],
            c=day_ctpi,
            cmap='RdYlGn_r',
            s=80,
            alpha=0.7
        )
        axes[0].set_title('白天时段 (08:00-18:00)', fontsize=12)
        axes[0].grid(True, alpha=0.3)
        
        # 夜间
        scatter = axes[1].scatter(
            communities['lng'],
            communities['lat'],
            c=night_ctpi,
            cmap='RdYlGn_r',
            s=80,
            alpha=0.7
        )
        axes[1].set_title('夜间时段 (18:00-22:00)', fontsize=12)
        axes[1].grid(True, alpha=0.3)
        
        # 统一颜色范围
        vmax = max(day_ctpi.max(), night_ctpi.max())
        vmin = min(day_ctpi.min(), night_ctpi.min())
        axes[0].set_clim(vmin, vmax)
        axes[1].set_clim(vmin, vmax)
        
        cbar = plt.colorbar(scatter, ax=axes[1], shrink=0.7)
        cbar.set_label('时间贫困指数', fontsize=10)
        
        plt.suptitle('白天vs夜间时间贫困对比', fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return fig, axes


# ============================================================================
# 第九部分：主程序
# ============================================================================

def main():
    """主程序入口"""
    
    print("="*70)
    print("15分钟城市时间贫困研究 - 核心计算框架")
    print("="*70)
    
    # 1. 初始化配置
    print("\n[1/6] 初始化配置...")
    config = Config()
    
    # 2. 加载POI数据
    print("\n[2/6] 加载POI数据...")
    if os.path.exists(config.POI_CSV):
        poi_df = DataLoader.load_poi_from_csv(config.POI_CSV)
    else:
        print(f"[WARN] POI CSV不存在: {config.POI_CSV}")
        print("   请先从Access数据库导出POI数据")
        poi_df = None
    
    # 3. 坐标转换
    print("\n[3/6] 坐标系转换...")
    transformer = CoordinateTransformer(config.SRC_CRS, config.DST_CRS)
    
    if poi_df is not None and 'lng' in poi_df.columns:
        poi_df = transformer.transform_df(poi_df, 'lng', 'lat')
    
    # 4. 构建道路网络
    print("\n[4/6] 构建道路网络...")
    network_analyzer = NetworkAnalyzer()
    
    # 5. 计算时间可达性
    print("\n[5/6] 计算时间可达性...")
    if poi_df is not None:
        calculator = TimeAccessibilityCalculator(network_analyzer)
        
        # 示例：计算某社区的可达性
        example_community = {
            'lng': 113.93,
            'lat': 22.53,
            'type': 'urban_village'
        }
        
        print("\n   示例计算（城中村，便利店，白天时段）:")
        result = calculator.calculate_effective_time(
            example_community,
            {'lng': 113.935, 'lat': 22.532, 'type': 'convenience_store', 'opening_hours': '08:00-23:00'},
            'day'
        )
        
        if result['available']:
            print(f"   移动时间: {result['travel_time']:.1f} 分钟")
            print(f"   曲折系数: {result['detour_factor']}")
            print(f"   等待时间: {result['wait_time']} 分钟")
            print(f"   办理时间: {result['service_time']} 分钟")
            print(f"   有效服务时间: {result['effective_time']:.1f} 分钟")
    
    # 6. 时间贫困指数
    print("\n[6/6] 时间贫困指数计算...")
    tpi = TimePovertyIndex(calculator if 'calculator' in dir() else None)
    
    # 7. 可视化
    print("\n[7/7] 生成可视化...")
    
    # 创建示例数据用于可视化
    np.random.seed(42)
    n_communities = 100
    
    communities = pd.DataFrame({
        'community_id': range(n_communities),
        'lng': 113.93 + np.random.randn(n_communities) * 0.02,
        'lat': 22.53 + np.random.randn(n_communities) * 0.01,
        'type': np.random.choice(['urban_village', 'normal_community', 'high_end'], n_communities),
        'ctpi_day': np.random.uniform(0.3, 0.9, n_communities),
        'ctpi_night': np.random.uniform(0.4, 1.0, n_communities)
    })
    
    # 绘制对比图
    try:
        fig, axes = Visualizer.plot_day_night_comparison(
            communities['ctpi_day'].values,
            communities['ctpi_night'].values,
            communities
        )
        plt.savefig('day_night_comparison.png', dpi=150, bbox_inches='tight')
        print("   ✅ 已保存: day_night_comparison.png")
    except Exception as e:
        print(f"   ⚠️ 可视化失败: {e}")
    
    print("\n" + "="*70)
    print("计算完成！")
    print("="*70)
    print("""
下一步:
1. 安装依赖: pip install geopandas osmnx contextily
2. 从Access数据库导出POI数据为CSV
3. 运行完整分析脚本
4. 生成研究区域的时间和贫困地图
    """)


# ============================================================================
# 辅助函数
# ============================================================================

def import_check():
    """检查所需依赖是否已安装"""
    required = {
        'numpy': '数值计算',
        'pandas': '数据处理',
        'matplotlib': '可视化',
        'geopandas': '地理数据处理',
        'osmnx': '路网分析',
        'networkx': '网络分析',
        'shapely': '几何操作',
        'pyproj': '坐标转换'
    }
    
    missing = []
    for lib, desc in required.items():
        try:
            __import__(lib)
            print(f"   [OK] {lib}: {desc}")
        except ImportError:
            print(f"   [MISSING] {lib}: {desc} (need install)")
            missing.append(lib)
    
    if missing:
        print(f"\n请安装缺失的依赖:")
        print(f"   pip install {' '.join(missing)}")
        return False
    return True


if __name__ == "__main__":
    import os
    
    print("依赖检查:")
    import_check()
    
    print("\n" + "-"*70)
    main()
