# -*- coding: utf-8 -*-
"""
OSM数据下载脚本
================

从OpenStreetMap获取深圳市的基础地理数据：
- 道路网络 (用于网络分析)
- POI兴趣点 (含设施分类)
- 建筑轮廓 (用于社区识别)

使用OSMNX库直接下载，数据源为OpenStreetMap

安装依赖:
    pip install osmnx geopandas shapely pandas

使用方法:
    python download_osm_data.py
"""

import os
import sys
import time
import warnings
warnings.filterwarnings('ignore')

# UTF-8编码设置
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

try:
    import osmnx as ox
    import geopandas as gpd
    from shapely.geometry import box, Point
    import pandas as pd
    print("[OK] 依赖检查通过")
except ImportError as e:
    print(f"[ERROR] 缺少依赖: {e}")
    print("请运行: pip install osmnx geopandas shapely pandas")
    sys.exit(1)

# 配置
class Config:
    """全局配置"""
    
    # 输出目录
    OUTPUT_DIR = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data"
    
    # 研究区域 - 深圳市南山区 (较小范围，避免超时)
    STUDY_AREA = "Nanshan District, Shenzhen, Guangdong, China"
    
    # 南山区边界框 (更精确的范围)
    BBOX = {
        'north': 22.54,
        'south': 22.48,
        'east': 113.98,
        'west': 113.85
    }
    
    # POI标签
    POI_TAGS = [
        {'amenity': True},           # 便利设施
        {'shop': True},               # 商店
        {'office': True},             # 办公
        {'tourism': True},            # 旅游
        {'leisure': True},            # 休闲
        {'sport': True},              # 体育
        {'healthcare': True},         # 医疗
        {'public_transport': True},   # 公共交通
    ]
    
    # 建筑标签
    BUILDING_TAGS = {'building': True}


class OSMDataDownloader:
    """OSM数据下载器"""
    
    def __init__(self, output_dir):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 配置OSMNX
        ox.settings.log_console = True
        ox.settings.use_cache = True
        ox.settings.cache_folder = os.path.join(output_dir, 'cache')
        
        print(f"输出目录: {output_dir}")
    
    def download_road_network(self, place_name=None, bbox=None):
        """
        下载道路网络
        
        参数:
            place_name: 地点名称 (如 "Shenzhen, China")
            bbox: 边界框 (north, south, east, west)
        
        返回:
            NetworkX图对象
        """
        print("\n" + "="*50)
        print("1. 下载道路网络")
        print("="*50)
        
        try:
            if bbox:
                # OSMNX 2.x: bbox参数为 (north, south, east, west) 元组
                bbox_tuple = (bbox['north'], bbox['south'], bbox['east'], bbox['west'])
                print(f"使用边界框: N{bbox['north']}, S{bbox['south']}, E{bbox['east']}, W{bbox['west']}")
                G = ox.graph_from_bbox(
                    bbox=bbox_tuple,
                    network_type='walk',
                    simplify=True
                )
            elif place_name:
                print(f"使用地点名称: {place_name}")
                G = ox.graph_from_place(
                    place_name,
                    network_type='walk',
                    simplify=True
                )
            else:
                raise ValueError("必须提供place_name或bbox")
            
            # 保存
            graphml_path = os.path.join(self.output_dir, 'road_network.graphml')
            gpkg_path = os.path.join(self.output_dir, 'road_network.gpkg')
            
            ox.save_graphml(G, graphml_path)
            ox.save_graph_geopackage(G, gpkg_path)
            
            print(f"✓ 路网保存完成:")
            print(f"  - GraphML: {graphml_path}")
            print(f"  - GeoPackage: {gpkg_path}")
            print(f"  - 节点数: {len(G.nodes)}")
            print(f"  - 边数: {len(G.edges)}")
            
            return G
            
        except Exception as e:
            print(f"✗ 下载失败: {e}")
            return None
    
    def download_poi(self, place_name=None, bbox=None, tags=None):
        """
        下载POI兴趣点
        
        参数:
            place_name: 地点名称
            bbox: 边界框
            tags: POI标签列表
        
        返回:
            GeoDataFrame
        """
        print("\n" + "="*50)
        print("2. 下载POI兴趣点")
        print("="*50)
        
        if tags is None:
            tags = Config.POI_TAGS
        
        all_pois = []
        
        for i, tag_dict in enumerate(tags):
            tag_name = list(tag_dict.keys())[0]
            tag_value = list(tag_dict.values())[0]
            print(f"\n下载标签 [{i+1}/{len(tags)}]: {tag_name}={tag_value}")
            
            try:
                if bbox:
                    bbox_tuple = (bbox['north'], bbox['south'], bbox['east'], bbox['west'])
                    features = ox.features_from_bbox(
                        bbox=bbox_tuple,
                        tags=tag_dict
                    )
                elif place_name:
                    features = ox.features_from_place(
                        place_name,
                        tags=tag_dict
                    )
                else:
                    continue
                
                if len(features) > 0:
                    all_pois.append(features)
                    print(f"  ✓ 获取 {len(features)} 个要素")
                else:
                    print(f"  - 无数据")
                    
            except Exception as e:
                print(f"  ✗ 失败: {e}")
            
            time.sleep(0.5)  # 避免请求过快
        
        if not all_pois:
            print("✗ 未获取到任何POI数据")
            return None
        
        # 合并
        gdf_poi = pd.concat(all_pois, ignore_index=True)
        gdf_poi = gpd.GeoDataFrame(gdf_poi, crs="EPSG:4326")
        
        # 保存
        shp_path = os.path.join(self.output_dir, 'poi.shp')
        gpkg_path = os.path.join(self.output_dir, 'poi.gpkg')
        csv_path = os.path.join(self.output_dir, 'poi.csv')
        
        gdf_poi.to_file(shp_path, encoding='utf-8')
        gdf_poi.to_file(gpkg_path, encoding='utf-8')
        
        # 保存为CSV (不含几何列)
        gdf_poi.drop(columns=['geometry'], errors='ignore').to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        print(f"\n✓ POI保存完成:")
        print(f"  - SHP: {shp_path}")
        print(f"  - GeoPackage: {gpkg_path}")
        print(f"  - CSV: {csv_path}")
        print(f"  - 总记录数: {len(gdf_poi)}")
        
        # 统计POI类型
        if 'amenity' in gdf_poi.columns:
            print(f"\n  设施类型统计 (amenity):")
            counts = gdf_poi['amenity'].value_counts().head(10)
            for name, count in counts.items():
                print(f"    - {name}: {count}")
        
        return gdf_poi
    
    def download_buildings(self, place_name=None, bbox=None):
        """
        下载建筑轮廓
        
        参数:
            place_name: 地点名称
            bbox: 边界框
        
        返回:
            GeoDataFrame
        """
        print("\n" + "="*50)
        print("3. 下载建筑轮廓")
        print("="*50)
        
        try:
            if bbox:
                print(f"使用边界框下载建筑...")
                bbox_tuple = (bbox['north'], bbox['south'], bbox['east'], bbox['west'])
                features = ox.features_from_bbox(
                    bbox=bbox_tuple,
                    tags=Config.BUILDING_TAGS
                )
            elif place_name:
                print(f"使用地点名称下载建筑...")
                features = ox.features_from_place(
                    place_name,
                    tags=Config.BUILDING_TAGS
                )
            else:
                raise ValueError("必须提供place_name或bbox")
            
            if len(features) == 0:
                print("✗ 未获取到建筑数据")
                return None
            
            gdf_buildings = gpd.GeoDataFrame(features, crs="EPSG:4326")
            
            # 保存
            shp_path = os.path.join(self.output_dir, 'buildings.shp')
            gpkg_path = os.path.join(self.output_dir, 'buildings.gpkg')
            
            gdf_buildings.to_file(shp_path, encoding='utf-8')
            gdf_buildings.to_file(gpkg_path, encoding='utf-8')
            
            print(f"\n✓ 建筑保存完成:")
            print(f"  - SHP: {shp_path}")
            print(f"  - GeoPackage: {gpkg_path}")
            print(f"  - 总记录数: {len(gdf_buildings)}")
            
            # 统计
            if 'building' in gdf_buildings.columns:
                print(f"\n  建筑类型统计:")
                counts = gdf_buildings['building'].value_counts().head(10)
                for name, count in counts.items():
                    print(f"    - {name}: {count}")
            
            return gdf_buildings
            
        except Exception as e:
            print(f"✗ 下载失败: {e}")
            return None
    
    def download_all(self):
        """下载所有数据"""
        print("\n" + "="*70)
        print("OSM数据下载 - 深圳市南山区")
        print("="*70)
        
        # 使用边界框 (更精确)
        bbox = Config.BBOX
        
        # 1. 下载道路网络
        road_G = self.download_road_network(bbox=bbox)
        
        # 2. 下载POI
        poi_gdf = self.download_poi(bbox=bbox)
        
        # 3. 下载建筑
        buildings_gdf = self.download_buildings(bbox=bbox)
        
        # 生成摘要
        print("\n" + "="*70)
        print("下载完成 - 数据摘要")
        print("="*70)
        
        summary = f"""
数据输出目录: {self.output_dir}

下载的数据:
  ✓ 道路网络: {len(road_G.nodes) if road_G else 0} 节点, {len(road_G.edges) if road_G else 0} 边
  ✓ POI兴趣点: {len(poi_gdf) if poi_gdf is not None else 0} 条
  ✓ 建筑轮廓: {len(buildings_gdf) if buildings_gdf is not None else 0} 栋

数据来源: OpenStreetMap (CC BY-SA 4.0)
坐标系: WGS84 (EPSG:4326)

下一步:
  1. 安装高德API Python SDK: pip install requests
  2. 申请高德API Key: https://lbs.amap.com
  3. 运行 collect_amap_hours.py 采集设施营业时间
  4. 运行 core_framework.py 进行时间贫困分析
        """
        
        print(summary)
        
        # 保存摘要
        with open(os.path.join(self.output_dir, 'download_summary.txt'), 'w', encoding='utf-8') as f:
            f.write(summary)
        
        return road_G, poi_gdf, buildings_gdf


def main():
    """主程序"""
    print("\n" + "="*70)
    print("OSM数据下载工具")
    print("15分钟城市时间贫困研究")
    print("="*70 + "\n")
    
    # 创建下载器
    downloader = OSMDataDownloader(Config.OUTPUT_DIR)
    
    # 下载所有数据
    road_G, poi_gdf, buildings_gdf = downloader.download_all()
    
    print("\n" + "="*70)
    print("下载任务完成!")
    print("="*70)


if __name__ == "__main__":
    main()
