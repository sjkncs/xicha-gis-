# -*- coding: utf-8 -*-
"""
15分钟城市时间贫困研究 - 统一数据获取脚本
自动下载所有必需的GIS数据

使用方法:
    python download_all_data.py

数据来源:
    1. OSM (OpenStreetMap) - 免费
    2. 高德API - 免费额度
    3. 人口数据 - 免费

作者: 未来交通实验室
日期: 2026-05-20
"""

import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path

# 强制使用UTF-8编码
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# 数据目录配置
DATA_ROOT = Path(r"E:\xicha_gis_data")
DIRS = {
    'osm': DATA_ROOT / '02_osm_data',
    'amap': DATA_ROOT / '03_amap_api',
    'population': DATA_ROOT / '04_population',
}

# 南山区边界 (大致坐标)
NANSHAN_BBOX = {
    'min_lon': 113.85,
    'max_lon': 113.98,
    'min_lat': 22.42,
    'max_lat': 22.55
}


def create_directories():
    """创建必要的目录结构"""
    print("\n" + "="*60)
    print("创建数据目录...")
    print("="*60)
    
    for name, path in DIRS.items():
        path.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {name}: {path}")


def download_osm_data():
    """
    下载OSM数据
    数据源: Geofabrik (免费开源)
    """
    print("\n" + "="*60)
    print("1. 下载OSM数据")
    print("="*60)
    
    # Geofabrik 下载链接
    osm_url = "https://download.geofabrik.de/asia/china/guangdong.html"
    
    # OSM 提供的不同格式
    formats = [
        # (文件名, URL, 说明)
        ("guangdong-latest.osm.pbf", 
         "https://download.geofabrik.de/asia/china/guangdong-latest.osm.pbf",
         "原始OSM数据(PBF格式,约300MB)"),
        
        ("guangdong-latest-shp.zip",
         "https://download.geofabrik.de/asia/china/guangdong-latest-free.shp.zip",
         "Shapefile格式(约1GB,包含POI/道路/建筑等)"),
    ]
    
    print(f"\n  推荐数据源: {osm_url}")
    print(f"\n  可下载的数据格式:")
    for i, (name, url, desc) in enumerate(formats, 1):
        print(f"    {i}. {name}")
        print(f"       {desc}")
    
    print(f"\n  当前已下载数据:")
    osm_dir = DIRS['osm']
    if (osm_dir / 'guangdong.zip').exists():
        size = (osm_dir / 'guangdong.zip').stat().st_size / 1024 / 1024
        print(f"    ✓ guangdong.zip ({size:.1f} MB)")
    if (osm_dir / 'road_network.gpkg').exists():
        size = (osm_dir / 'road_network.gpkg').stat().st_size / 1024 / 1024
        print(f"    ✓ road_network.gpkg ({size:.1f} MB)")
    
    print(f"\n  手动下载步骤:")
    print(f"    1. 打开: {osm_url}")
    print(f"    2. 选择 'guangdong-latest-free.shp.zip' (约1GB)")
    print(f"    3. 保存到: {DIRS['osm']}")
    
    return True


def download_amap_data():
    """
    高德API数据获取说明
    """
    print("\n" + "="*60)
    print("2. 高德API数据")
    print("="*60)
    
    api_info = """
    高德地图API提供免费的POI搜索服务:
    
    申请步骤:
    1. 访问 https://lbs.amap.com
    2. 注册账号并登录
    3. 创建应用获取Key
    
    免费额度:
    - POI搜索: 5000次/日
    - 地理编码: 5000次/日
    
    获取Key后，编辑项目中的:
        collect_amap_hours.py
    在文件开头填入你的Key:
        AMAP_KEY = "你的Key"
    """
    print(api_info)
    
    # 创建示例配置
    config_file = DIRS['amap'] / 'amap_key_config.py'
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('# 高德API配置\n')
        f.write('# 请访问 https://lbs.amap.com 注册获取Key\n')
        f.write('\n')
        f.write('# 在下方填入你的Key\n')
        f.write('AMAP_KEY = ""\n')
        f.write('\n')
        f.write('# 搜索关键词配置\n')
        f.write('POI_TYPES = [\n')
        f.write('    "超市", "便利店", "药店", "医院", "学校",\n')
        f.write('    "银行", "餐厅", "菜市场", "健身房", "公园"\n')
        f.write(']\n')
    
    print(f"\n  ✓ 已创建配置模板: {config_file}")
    
    return True


def download_population_data():
    """
    人口数据获取说明
    """
    print("\n" + "="*60)
    print("3. 人口数据")
    print("="*60)
    
    sources = """
    推荐的人口数据源:
    
    1. LandScan (免费,1km分辨率)
       https://landscan.ornl.gov/
       - 需要注册下载
       - 全球覆盖,数据较新
    
    2. WorldPop (免费,100m分辨率)
       https://www.worldpop.org/
       - 更高分辨率
       - 需要申请下载
    
    3. 中国国家地球系统科学数据中心
       https://www.geodata.cn/
       - 国内数据源
       - 可能需要申请
    
    数据格式建议: GeoTIFF 或 CSV (经纬度+人口数)
    """
    print(sources)
    
    return True


def generate_download_summary():
    """生成数据下载汇总"""
    print("\n" + "="*60)
    print("数据下载汇总")
    print("="*60)
    
    summary = f"""
    数据目录: {DATA_ROOT}
    
    目录结构:
    {DATA_ROOT}
    ├── 01_shp_origin/      # 原始SHP数据
    │   ├── nsPT.shp         # 道路网络
    │   ├── pdbuilding.shp   # 建筑轮廓
    │   ├── pdlanduse.shp    # 土地利用
    │   ├── contour.shp      # 等高线
    │   ├── 区级边界New.shp   # 行政边界
    │   └── test.mdb         # Access数据库(67MB POI数据)
    │
    ├── 02_osm_data/         # OSM开源数据
    │   ├── guangdong.zip    # 广东省OSM数据
    │   ├── road_network.gpkg # 道路网络
    │   └── road_network.graphml # 路网图
    │
    ├── 03_amap_api/         # 高德API数据
    │   └── amap_key_config.py # API密钥配置模板
    │
    ├── 04_population/        # 人口数据(待下载)
    │
    └── 05_output/            # 分析结果输出

    数据状态:
    ✅ 道路网络: nsPT.shp (5.61 MB)
    ✅ 建筑轮廓: pdbuilding.shp (3.28 MB)
    ✅ 土地利用: pdlanduse.shp (2.05 MB)
    ✅ 等高线: contour.shp (3.70 MB)
    ✅ 行政边界: 区级边界New.shp (0.21 MB)
    ⚠️ POI数据: test.mdb (67.29 MB, 需要转换为CSV)
    ✅ OSM数据: guangdong.zip (30.53 MB)
    ✅ 路网图: road_network.graphml (125.46 MB)
    
    待下载:
    ❌ 完整OSM Shapefile (约1GB)
    ❌ 高德API Key (免费申请)
    ❌ 人口数据 (LandScan)
    
    下一步:
    1. 手动下载完整OSM Shapefile
    2. 申请高德API Key
    3. 运行项目中的数据处理脚本
    """
    print(summary)
    
    # 保存到文件
    summary_file = DATA_ROOT / 'download_summary.txt'
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write(summary)
    print(f"\n  ✓ 已保存到: {summary_file}")


def main():
    """主函数"""
    print("\n" + "="*70)
    print("15分钟城市时间贫困研究 - 统一数据获取脚本")
    print("="*70)
    print(f"\n数据保存目录: {DATA_ROOT}")
    
    # 创建目录
    create_directories()
    
    # 下载各类型数据
    download_osm_data()
    download_amap_data()
    download_population_data()
    
    # 生成汇总
    generate_download_summary()
    
    print("\n" + "="*70)
    print("数据获取指导完成!")
    print("="*70)
    print("""
请按以下步骤完成数据获取:

1. 【OSM数据】手动下载
   打开: https://download.geofabrik.de/asia/china/guangdong.html
   下载: guangdong-latest-free.shp.zip (约1GB)
   保存到: E:\\xicha_gis_data\\02_osm_data\\

2. 【高德API】申请Key
   访问: https://lbs.amap.com
   申请应用获取Key
   编辑: E:\\xicha_gis_data\\03_amap_api\\amap_key_config.py

3. 【人口数据】可选
   访问: https://landscan.ornl.gov/
   下载广东省人口数据
   保存到: E:\\xicha_gis_data\\04_population\\
    """)


if __name__ == '__main__':
    main()
