# -*- coding: utf-8 -*-
"""
Geofabrik OSM数据直接下载脚本
==========================

直接从Geofabrik下载预制的中国/广东省数据，然后裁剪到深圳市南山区

优势:
- 更快: 无需通过Overpass API逐块请求
- 更稳定: 预制数据，无需担心超时
- 完整: 包含所有数据类型

使用方法:
    python download_geofabrik.py
"""

import os
import sys
import time
import zipfile
import requests
import geopandas as gpd
from shapely.geometry import box, shape
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

# UTF-8编码设置
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'


class GeofabrikDownloader:
    """Geofabrik数据下载器"""
    
    # Geofabrik下载URL
    BASE_URL = "https://download.geofabrik.de/asia/china"
    
    # 研究区域配置
    OUTPUT_DIR = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data"
    
    # 深圳市南山区精确边界
    NANSHAN_BBOX = {
        'minx': 113.85,  # 西
        'maxx': 113.98,  # 东
        'miny': 22.48,   # 南
        'maxy': 22.54    # 北
    }
    
    def __init__(self):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        print(f"输出目录: {self.OUTPUT_DIR}")
    
    def download_file(self, url, save_path, chunk_size=8192):
        """下载文件"""
        print(f"正在下载: {url}")
        
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size:
                        pct = downloaded / total_size * 100
                        print(f"\r下载进度: {pct:.1f}% ({downloaded/1024/1024:.1f}MB)", end='', flush=True)
        
        print()  # 换行
        return save_path
    
    def download_guangdong(self):
        """下载广东省SHP数据"""
        print("\n" + "="*60)
        print("1. 下载广东省OSM数据 (SHP格式)")
        print("="*60)
        
        url = f"{self.BASE_URL}/guangdong-latest-free.shp.zip"
        zip_path = os.path.join(self.OUTPUT_DIR, "guangdong.zip")
        
        if os.path.exists(zip_path):
            print(f"文件已存在: {zip_path}")
            return zip_path
        
        self.download_file(url, zip_path)
        return zip_path
    
    def extract_shapefile(self, zip_path):
        """从zip文件提取shapefile"""
        print("\n" + "="*60)
        print("2. 提取Shapefile数据")
        print("="*60)
        
        extract_dir = os.path.join(self.OUTPUT_DIR, "guangdong_shp")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 列出提取的文件
        files = []
        for root, dirs, filenames in os.walk(extract_dir):
            for f in filenames:
                if f.endswith('.shp'):
                    files.append(os.path.join(root, f))
        
        print(f"提取完成，找到 {len(files)} 个SHP文件:")
        for f in files:
            print(f"  - {os.path.basename(f)}")
        
        return extract_dir
    
    def filter_nanshan(self, shapefile_path, output_name):
        """按南山区边界裁剪数据"""
        print(f"\n正在裁剪: {os.path.basename(shapefile_path)}")
        
        try:
            # 读取数据
            gdf = gpd.read_file(shapefile_path)
            print(f"  原始记录数: {len(gdf)}")
            
            if len(gdf) == 0:
                print("  [WARN] 数据为空")
                return None
            
            # 创建裁剪边界
            bounds = self.NANSHAN_BBOX
            clip_box = box(bounds['minx'], bounds['miny'], 
                         bounds['maxx'], bounds['maxy'])
            
            # 空间裁剪
            if gdf.crs and gdf.crs != "EPSG:4326":
                gdf = gdf.to_crs("EPSG:4326")
            
            gdf_clipped = gdf[gdf.geometry.intersects(clip_box)].copy()
            print(f"  裁剪后记录数: {len(gdf_clipped)}")
            
            if len(gdf_clipped) == 0:
                print("  [WARN] 裁剪后无数据，可能需要调整边界")
                return None
            
            # 保存
            output_path = os.path.join(self.OUTPUT_DIR, output_name)
            gdf_clipped.to_file(output_path, encoding='utf-8')
            print(f"  已保存: {output_path}")
            
            return gdf_clipped
            
        except Exception as e:
            print(f"  [ERROR] 处理失败: {e}")
            return None
    
    def download_all(self):
        """下载并处理所有数据"""
        print("\n" + "="*70)
        print("Geofabrik OSM数据下载 - 深圳市南山区")
        print("="*70)
        
        # 1. 下载广东省数据
        zip_path = self.download_guangdong()
        
        # 2. 提取数据
        extract_dir = self.extract_shapefile(zip_path)
        
        # 3. 查找并裁剪数据文件
        print("\n" + "="*60)
        print("3. 裁剪到南山区范围")
        print("="*60)
        
        shapefiles_to_process = [
            # (源文件名模式, 输出文件名)
            ('gis_osm_roads_free.shp', 'nanshan_roads.shp'),
            ('gis_osm_pois_a_free.shp', 'nanshan_pois.shp'),
            ('gis_osm_pois_free.shp', 'nanshan_pois.shp'),
            ('gis_osm_buildings_a_free.shp', 'nanshan_buildings.shp'),
            ('gis_osm_buildings_free.shp', 'nanshan_buildings.shp'),
        ]
        
        results = {}
        for pattern, output_name in shapefiles_to_process:
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    if f == pattern or f.startswith(pattern.split('.')[0]):
                        full_path = os.path.join(root, f)
                        result = self.filter_nanshan(full_path, output_name)
                        if result is not None:
                            results[output_name] = result
                        break
        
        # 打印摘要
        print("\n" + "="*70)
        print("下载完成 - 数据摘要")
        print("="*70)
        
        for name, gdf in results.items():
            if gdf is not None:
                print(f"  - {name}: {len(gdf)} 条记录")
        
        print(f"""
数据输出目录: {self.OUTPUT_DIR}

下一步:
1. 申请高德API Key: https://lbs.amap.com
2. 运行 collect_amap_hours.py 采集设施营业时间
3. 运行 core_framework.py 进行时间贫困分析
        """)
        
        return results


def main():
    """主程序"""
    downloader = GeofabrikDownloader()
    downloader.download_all()


if __name__ == "__main__":
    main()
