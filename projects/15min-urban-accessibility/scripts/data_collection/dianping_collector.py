# -*- coding: utf-8 -*-
"""
大众点评数据采集模块
=================

支持获取大众点评POI数据中的设施信息（名称、位置、营业时间等）

注意: 大众点评API需要申请开发者权限，此模块提供数据接口定义和模拟数据生成

使用方法:
    python dianping_collector.py
"""

import os
import sys
import json
import time
import math
import random
from typing import List, Dict, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DianpingPOI:
    """大众点评POI数据模型"""
    shop_id: str
    shop_name: str
    category_name: str  # 分类名称，如"便利店"、"药店"
    branch_name: str   # 分店名
    address: str
    longitude: float
    latitude: float
    avg_price: float   # 人均价格
    rating: float       # 评分
    open_time: str      # 营业时间
    service_tags: List[str]  # 服务标签


class DianpingCollector:
    """大众点评数据采集器"""
    
    # 大众点评分类编码
    CATEGORY_CODES = {
        '便利店': 'GS01050000',      # 超市/便利店
        '药店': 'GS01080000',        # 药品零售
        '医院': 'GS05000000',        # 医疗保健
        '银行': 'GS02000000',        # 金融
        'ATM': 'GS02010000',         # ATM
        '快递': 'GS08000000',        # 物流快递
        '超市': 'GS01050000',        # 超市
        '菜市场': 'GS01030000',      # 农贸市场
    }
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
        })
    
    def search_by_keyword(self, keyword: str, city: str = "深圳", 
                         page: int = 1, page_size: int = 32) -> List[DianpingPOI]:
        """
        通过关键词搜索POI
        
        参数:
            keyword: 搜索关键词
            city: 城市名
            page: 页码
            page_size: 每页数量
        
        返回:
            List[DianpingPOI]: POI列表
        """
        # 注意: 大众点评API需要申请，这里是接口定义
        # 实际使用时需要申请大众点评开发者权限
        logger.warning("大众点评官方API需要申请开发者权限")
        logger.info("使用模拟数据演示")
        
        return self._generate_mock_data(keyword, count=min(page_size, 20))
    
    def _generate_mock_data(self, keyword: str, count: int = 20) -> List[DianpingPOI]:
        """生成模拟数据（用于演示）"""
        pois = []
        
        # 便利店类型
        convenience_names = [
            '7-ELEVEN', '全家', '罗森', '便利蜂', '天猫小店',
            '苏宁小店', '京东便利店', '美宜佳', '天福', '上好',
            ' Wink', '好的', '快迪', '人本', '乐客'
        ]
        
        # 药店类型
        pharmacy_names = [
            '大参林', '老百姓大药房', '海王星辰', '一心堂', '益丰大药房',
            '国大药房', '华润万家药房', '金康药房', '宝华药房', '仁和药房'
        ]
        
        # 快递类型
        express_names = [
            '顺丰速运', '京东快递', '圆通速递', '中通快递', '韵达快递',
            '申通快递', '百世快递', '德邦快递', '邮政EMS', '极兔速递'
        ]
        
        names = convenience_names if keyword in ['便利店', '超市'] else \
                pharmacy_names if keyword in ['药店', '医院'] else \
                express_names if keyword in ['快递'] else \
                [f'{keyword}_{i}' for i in range(count)]
        
        base_lng, base_lat = 113.93, 22.53  # 深圳南山
        
        for i in range(count):
            name = random.choice(names) if len(names) >= count else names[i]
            
            poi = DianpingPOI(
                shop_id=f"dp_{keyword}_{i}",
                shop_name=name,
                category_name=keyword,
                branch_name="",
                address=f"深圳市南山区xxx路{i+1}号",
                longitude=base_lng + random.uniform(-0.05, 0.05),
                latitude=base_lat + random.uniform(-0.03, 0.03),
                avg_price=random.choice([0, 15, 25, 50, 100, 200]),
                rating=round(random.uniform(3.5, 5.0), 1),
                open_time=self._generate_opening_hours(keyword),
                service_tags=self._generate_service_tags(keyword)
            )
            pois.append(poi)
        
        return pois
    
    def _generate_opening_hours(self, category: str) -> str:
        """生成模拟营业时间"""
        hours_options = {
            '便利店': ['24小时', '07:00-23:00', '08:00-22:00', '06:00-24:00'],
            '药店': ['08:00-21:00', '09:00-22:00', '24小时', '08:00-22:00'],
            '医院': ['08:00-18:00', '24小时', '00:00-24:00', '24小时'],
            '银行': ['09:00-17:00', '09:00-17:30', '09:00-16:00'],
            'ATM': ['24小时', '00:00-24:00', '24小时'],
            '快递': ['09:00-21:00', '08:00-22:00', '10:00-20:00'],
            '超市': ['08:00-22:00', '07:00-23:00', '09:00-21:00'],
            '菜市场': ['06:00-12:00', '05:00-11:00', '07:00-13:00'],
        }
        
        options = hours_options.get(category, ['09:00-18:00'])
        return random.choice(options)
    
    def _generate_service_tags(self, category: str) -> List[str]:
        """生成服务标签"""
        tags_options = {
            '便利店': ['24小时营业', '支持外卖', '支持自提', '支持回收'],
            '药店': ['医保定点', '支持外卖', '24小时营业', '专业药师'],
            '医院': ['急诊', '支持医保', '专家门诊'],
            '银行': ['支持医保卡', '外汇服务'],
            '快递': ['上门取件', '当日达', '次日达', '生鲜速配'],
        }
        
        options = tags_options.get(category, [])
        return random.sample(options, min(len(options), random.randint(1, 3)))
    
    def collect_shenzhen_facilities(self, output_dir: str) -> pd.DataFrame:
        """采集深圳各类设施数据"""
        all_facilities = []
        
        keywords = ['便利店', '药店', '医院', '银行', 'ATM', '快递', '超市', '菜市场']
        
        logger.info("="*60)
        logger.info("大众点评数据采集")
        logger.info("="*60)
        
        for keyword in keywords:
            logger.info(f"采集: {keyword}")
            pois = self.search_by_keyword(keyword, city="深圳")
            
            for poi in pois:
                facility = {
                    'source': 'dianping',
                    'shop_id': poi.shop_id,
                    'name': poi.shop_name,
                    'category': keyword,
                    'facility_type': self._map_to_facility_type(keyword),
                    'lng': poi.longitude,
                    'lat': poi.latitude,
                    'address': poi.address,
                    'open_time': poi.open_time,
                    'is_24h': '24' in poi.open_time,
                    'rating': poi.rating,
                    'avg_price': poi.avg_price,
                    'service_tags': ','.join(poi.service_tags)
                }
                all_facilities.append(facility)
            
            logger.info(f"  已累计: {len(all_facilities)} 条")
            time.sleep(0.3)
        
        df = pd.DataFrame(all_facilities)
        
        # 保存
        csv_path = os.path.join(output_dir, 'dianping_facilities.csv')
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"✓ 保存: {csv_path}")
        
        return df
    
    def _map_to_facility_type(self, category: str) -> str:
        """映射到标准设施类型"""
        mapping = {
            '便利店': 'convenience_store',
            '超市': 'supermarket',
            '药店': 'pharmacy',
            '医院': 'hospital',
            '银行': 'bank',
            'ATM': 'atm',
            '快递': 'express',
            '菜市场': 'market',
        }
        return mapping.get(category, 'other')


# ============================================================================
# 小区AOI数据处理模块
# ============================================================================

class CommunityAOIPreprocessor:
    """
    小区AOI数据预处理器
    
    用于处理小区边界数据，支持：
    1. 从OSM建筑数据聚类生成小区边界
    2. 加载商用小区AOI数据
    3. 计算小区质心和面积
    4. 识别社区类型
    """
    
    def __init__(self, config):
        self.config = config
    
    def cluster_buildings_to_communities(self, buildings_gdf: gpd.GeoDataFrame,
                                         min_buildings: int = 5) -> gpd.GeoDataFrame:
        """
        将建筑聚类为小区
        
        使用DBSCAN聚类算法，基于建筑位置和面积进行聚类
        """
        from sklearn.cluster import DBSCAN
        
        logger.info("将建筑聚类为小区...")
        
        # 提取建筑中心点
        buildings = buildings_gdf.copy()
        buildings['centroid'] = buildings.geometry.centroid
        buildings['lng'] = buildings['centroid'].x
        buildings['lat'] = buildings['centroid'].y
        
        # 计算建筑面积
        if buildings.geometry.geom_type.iloc[0] == 'Polygon':
            buildings['area'] = buildings.geometry.area
        else:
            buildings['area'] = 100  # 默认面积
        
        # DBSCAN聚类
        coords = buildings[['lng', 'lat']].values
        
        # 根据研究区域调整eps参数（大约500米）
        eps_deg = 0.005  # 约500米
        clustering = DBSCAN(eps=eps_deg, min_samples=min_buildings).fit(coords)
        
        buildings['cluster'] = clustering.labels_
        
        # 生成小区
        communities = []
        cluster_ids = buildings['cluster'].unique()
        
        for cluster_id in cluster_ids:
            if cluster_id == -1:  # 噪声点
                continue
            
            cluster_buildings = buildings[buildings['cluster'] == cluster_id]
            
            if len(cluster_buildings) < min_buildings:
                continue
            
            # 计算小区属性
            centroid = cluster_buildings['centroid'].unary_union.centroid
            total_area = cluster_buildings['area'].sum()
            avg_area = cluster_buildings['area'].mean()
            
            # 识别社区类型
            community_type = self._identify_community_type(
                len(cluster_buildings), 
                avg_area,
                total_area
            )
            
            community = {
                'cid': f'comm_{cluster_id}',
                'name': f'聚类小区{cluster_id}',
                'community_type': community_type,
                'building_count': len(cluster_buildings),
                'total_area_sqm': total_area,
                'avg_building_area': avg_area,
                'lng': centroid.x,
                'lat': centroid.y,
                'geometry': cluster_buildings['centroid'].unary_union
            }
            communities.append(community)
        
        communities_gdf = gpd.GeoDataFrame(communities, crs=buildings_gdf.crs)
        logger.info(f"✓ 生成 {len(communities_gdf)} 个小区")
        
        return communities_gdf
    
    def _identify_community_type(self, building_count: int, avg_area: float, 
                               total_area: float) -> str:
        """
        识别社区类型
        
        基于建筑特征判断：
        - 城中村: 建筑密度高、楼栋多、单栋面积小
        - 高端社区: 建筑密度低、楼栋少、单栋面积大
        """
        if building_count >= 20 and avg_area < 200:
            return 'urban_village'  # 城中村
        elif building_count >= 10 and avg_area >= 500:
            return 'high_end'  # 高端社区
        elif building_count >= 5:
            return 'normal_community'  # 普通商品房
        else:
            return 'old_community'  # 老旧小区
    
    def load_commercial_aoi(self, aoi_file: str) -> gpd.GeoDataFrame:
        """加载商用小区AOI数据"""
        logger.info(f"加载商用AOI数据: {aoi_file}")
        
        if not os.path.exists(aoi_file):
            logger.warning(f"文件不存在: {aoi_file}")
            return None
        
        try:
            gdf = gpd.read_file(aoi_file)
            
            # 标准化字段
            if 'name' not in gdf.columns and 'NAME' in gdf.columns:
                gdf['name'] = gdf['NAME']
            
            if 'community_type' not in gdf.columns:
                gdf['community_type'] = 'normal_community'
            
            # 计算质心
            gdf['lng'] = gdf.geometry.centroid.x
            gdf['lat'] = gdf.geometry.centroid.y
            
            logger.info(f"✓ 加载 {len(gdf)} 个小区AOI")
            return gdf
            
        except Exception as e:
            logger.error(f"加载失败: {e}")
            return None
    
    def merge_facilities_with_communities(self, 
                                         facilities_df: pd.DataFrame,
                                         communities_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
        """将设施分配到最近的小区"""
        from scipy.spatial import cKDTree
        
        logger.info("设施-小区匹配...")
        
        # 小区坐标
        comm_coords = communities_gdf[['lng', 'lat']].values
        comm_tree = cKDTree(comm_coords)
        
        # 设施坐标
        if 'lng' not in facilities_df.columns or facilities_df['lng'].isna().all():
            logger.warning("设施数据缺少坐标，跳过匹配")
            return facilities_df
        
        fac_coords = facilities_df[['lng', 'lat']].values
        
        # 查找最近小区
        distances, indices = comm_tree.query(fac_coords, k=1)
        
        facilities_df['nearest_comm_id'] = communities_gdf.iloc[indices]['cid'].values
        facilities_df['nearest_comm_name'] = communities_gdf.iloc[indices]['name'].values
        facilities_df['distance_to_comm'] = distances
        
        # 统计每个小区的设施数量
        facility_counts = facilities_df.groupby('nearest_comm_id').size()
        communities_gdf['facility_count'] = communities_gdf['cid'].map(facility_counts).fillna(0).astype(int)
        
        logger.info("✓ 设施-小区匹配完成")
        
        return facilities_df


def main():
    """测试数据采集"""
    output_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("\n" + "="*60)
    print("大众点评数据采集测试")
    print("="*60)
    
    collector = DianpingCollector()
    df = collector.collect_shenzhen_facilities(output_dir)
    
    print(f"\n采集完成: {len(df)} 条设施数据")
    print("\n各类型设施统计:")
    print(df['category'].value_counts())
    
    print("\n夜间服务设施统计:")
    print(f"24小时营业: {df['is_24h'].sum()}")
    print(f"占比: {df['is_24h'].mean()*100:.1f}%")


if __name__ == "__main__":
    main()
