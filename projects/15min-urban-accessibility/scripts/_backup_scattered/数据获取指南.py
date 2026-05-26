# -*- coding: utf-8 -*-
"""
国内开源/免费数据平台 - 数据获取指南
=====================================

本文件汇总了用于15分钟城市时间贫困研究的数据获取渠道

## 一、推荐数据源
"""

DATA_SOURCES = """
================================================================================
国内城市研究数据获取指南 (2026年5月更新)
================================================================================

┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. OpenStreetMap (OSM) - 首选推荐 [免费]                                      │
└──────────────────────────────────────────────────────────────────────────────┘

【数据下载】
  主站: https://www.openstreetmap.org
  Geofabrik下载: https://download.geofabrik.de/asia/china.html
  OSM中国数据: https://download.geofabrik.de/asia/china.html
  
【可获取数据】
  ✓ POI兴趣点 (64大类, 117种细分类型)
  ✓ 道路网络 (高速公路、国道、省道、县道、乡村道路)
  ✓ 建筑轮廓 (building footprints)
  ✓ 行政区边界 (省/市/县/乡镇)
  ✓ 土地利用/地表覆盖
  
【数据格式】
  • OSM PBF (.osm.pbf) - 推荐，小体积
  • SHP格式 (.shp.zip) - 约1GB
  • GeoJSON - 轻量级选择
  
【坐标系】
  • WGS84 (EPSG:4326)
  
【更新频率】
  • 每周更新快照
  • 2026年5月最新数据可用
  
【深圳数据下载】
  广东省: https://download.geofabrik.de/asia/china/guangdong.html
  深圳市: 可从广东省数据中裁剪

【Python下载示例】
  import osmnx as ox
  import geopandas as gpd
  
  # 下载深圳路网
  G = ox.graph_from_place("Shenzhen, Guangdong, China", network_type="walk")
  
  # 下载建筑
  buildings = ox.features_from_place("Shenzhen, China", tags={"building": True})

================================================================================
2. 高德地图API [免费额度+付费]                                                │
================================================================================

【申请入口】
  https://lbs.amap.com
  
【免费额度】
  • Web服务API: 5000次/日 (个人开发者)
  • 搜索服务: 5000次/日
  • 超出部分: 0.01元/次
  
【关键字段 - 营业时间】
  高德POI返回字段中包含: business_periods (营业时间)
  格式: "08:00-22:00" 或 "周一至周五 08:00-20:00"
  
【API端点】
  POST https://restapi.amap.com/v3/place/text
  参数: key, keywords, city, types, offset, page, extensions
  
【Python调用示例】
  import requests
  
  def search_amap_poi(keyword, city="深圳", key="YOUR_KEY"):
      url = "https://restapi.amap.com/v3/place/text"
      params = {
          "key": key,
          "keywords": keyword,
          "city": city,
          "offset": 20,
          "page": 1,
          "extensions": "all"  # 获取完整信息
      }
      resp = requests.get(url, params=params)
      return resp.json()

================================================================================
3. 百度地图API [免费额度]                                                    │
================================================================================

【申请入口】
  https://lbsyun.baidu.com
  
【免费额度】
  • POI检索: 20万次/日
  • 地点检索: 20万次/日
  
【关键字段】
  • business_time: 营业时间
  • detail_info包含更多扩展信息

================================================================================
4. 商用POI数据源 [付费]                                                    │
================================================================================

【CSDN数据商 - 全国POI/AOI数据】
  • 6674万POI (2025年12月更新)
  • 325万AOI (2025年5月更新)
  • 64.4万住宅小区AOI (2025年2月更新)
  • 包含42个字段，含运营时间
  博客: https://blog.csdn.net/lishenghu365/
  
【价格参考】
  • 单一城市POI: ¥500-2000
  • 全国POI: ¥5000-20000
  • 含小区边界AOI: 价格更高

================================================================================
5. AWS Open Data - OSM镜像 [免费]                                           │
================================================================================

【访问地址】
  https://registry.opendata.aws/osm/
  
【无需AWS账户，直接下载】
  s3://osm-pds/...
  
【数据格式】
  • PBF格式
  • 全球周更新快照

================================================================================
6. 人口与遥感数据 [免费]                                                    │
================================================================================

【LandScan人口数据】
  • 全球1km分辨率人口分布
  • 下载: https://landscan.ornl.gov/landscan-datasets/
  • 30弧秒分辨率，约1km
  
【LandScan HD China】
  • 中国专属高分辨率版本
  • 3弧秒分辨率，约90m
  • 需申请获取

【Sentinel-2卫星】
  • AWS Open Data免费获取
  • 10m分辨率多光谱

================================================================================
7. 其他开源资源                                                         │
================================================================================

【国家基础地理信息中心】
  • 全国1:100万基础地理数据
  • http://www.webmap.cn
  
【全国地理信息资源目录服务系统】
  • 30m全球地表覆盖数据
  • http://www.webmap.cn/main.do?method=index
  
【地理遥感数据云平台】
  • http://www.gscloud.cn
  • Landsat、Sentinel等遥感数据

================================================================================
二、数据获取推荐方案
================================================================================

【方案A: 纯开源方案 (推荐用于学术研究)】
  1. OSM数据获取:
     - 下载广东省SHP数据 (约200MB)
     - 裁剪出深圳市范围
     - 提取POI、道路、建筑
     
  2. 路网补充:
     - 使用OSMNX直接下载深圳OSM路网
     
  3. 营业时间获取:
     - 高德API申请免费Key
     - 按城市分批查询目标设施
     - 存储到本地CSV

【方案B: 开源+商业数据 (推荐用于完整研究)】
  1. 购买单一城市POI数据 (约¥500-2000)
  2. 包含完整字段和运营时间
  3. 配合OSM路网数据使用

【方案C: 全API方案 (适合小范围研究)】
  1. 高德API申请Key
  2. 按需查询设施POI
  3. 利用API返回的营业时间
  4. 注意免费额度限制

================================================================================
三、数据获取脚本
================================================================================

【OSM数据获取 - 使用OSMNX直接下载】
"""

OSMNX_DOWNLOAD = '''
# 安装: pip install osmnx geopandas
import osmnx as ox
import geopandas as gpd
from shapely.geometry import box

# 配置
ox.settings.log_console = True
ox.settings.use_cache = True

# 1. 下载深圳路网 (步行网络)
print("正在下载深圳步行路网...")
G = ox.graph_from_place("Shenzhen, Guangdong, China", network_type="walk")
ox.save_graphml(G, "shenzhen_walk_network.graphml")
ox.save_graph_geopackage(G, "shenzhen_walk_network.gpkg")

# 2. 下载建筑数据
print("正在下载建筑数据...")
buildings = ox.features_from_place(
    "Shenzhen, Guangdong, China",
    tags={"building": True}
)
buildings_gdf = gpd.GeoDataFrame(buildings)
buildings_gdf.to_file("shenzhen_buildings.shp")

# 3. 下载POI数据
print("正在下载POI数据...")
pois = ox.features_from_place(
    "Shenzhen, Guangdong, China",
    tags={
        "amenity": True,
        "shop": True,
        "office": True,
        "tourism": True,
        "leisure": True
    }
)
pois_gdf = gpd.GeoDataFrame(pois)
pois_gdf.to_file("shenzhen_pois.shp")

print("下载完成!")
'''

AMAP_API_SCRIPT = '''
# 高德API调用示例 - 获取设施营业时间
# 安装: pip install requests pandas

import requests
import pandas as pd
import time
import json

class AmapPOIClient:
    """高德地图POI搜索客户端"""
    
    BASE_URL = "https://restapi.amap.com/v3/place/text"
    
    # 设施类型编码
    TYPE_CODES = {
        "便利店": "060100",      # 便利超市
        "药店": "060101",        # 医药连锁店
        "医院": "090100",        # 综合医院
        "银行": "160100",        # 银行
        "超市": "060101",        # 超市
        "菜市场": "060103",      # 农贸市场
        "快递": "180000",        # 快递
        "学校": "150000",        # 教育
    }
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
    
    def search_poi(self, keywords, city="深圳", type_code=None, page=1):
        """
        搜索POI
        
        参数:
            keywords: 关键词
            city: 城市名
            type_code: 设施类型编码
            page: 页码
        """
        params = {
            "key": self.api_key,
            "keywords": keywords,
            "city": city,
            "citylimit": "true",
            "offset": 20,
            "page": page,
            "extensions": "all"  # 获取完整信息包括营业时间
        }
        if type_code:
            params["types"] = type_code
        
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=10)
            data = resp.json()
            
            if data.get("status") == "1":
                return data.get("pois", [])
            else:
                print(f"API错误: {data.get('info')}")
                return []
        except Exception as e:
            print(f"请求失败: {e}")
            return []
    
    def search_by_category(self, category, city="深圳", max_pages=10):
        """
        按类别搜索POI
        
        参数:
            category: 设施类别
            city: 城市
            max_pages: 最大页数
        """
        type_code = self.TYPE_CODES.get(category)
        all_pois = []
        
        for page in range(1, max_pages + 1):
            pois = self.search_poi(category, city, type_code, page)
            if not pois:
                break
            all_pois.extend(pois)
            time.sleep(0.2)  # 避免请求过快
        
        return all_pois
    
    def extract_opening_hours(self, poi):
        """
        提取POI的营业时间
        
        返回:
            dict: 包含开放时间的字典
        """
        info = poi.get("biz_ext", {})
        return {
            "name": poi.get("name"),
            "address": poi.get("address"),
            "location": poi.get("location"),
            "type": poi.get("type"),
            "business_period": info.get("business_period", ""),  # 营业时间
            "cost": info.get("cost", ""),  # 人均消费
        }


def main():
    # 使用示例
    API_KEY = "YOUR_AMAP_KEY"  # 替换为您的API Key
    
    client = AmapPOIClient(API_KEY)
    
    # 搜索各类设施
    categories = ["便利店", "药店", "医院", "超市", "银行", "快递"]
    all_facilities = []
    
    for category in categories:
        print(f"正在搜索: {category}")
        pois = client.search_by_category(category, "深圳", max_pages=5)
        for poi in pois:
            facility = client.extract_opening_hours(poi)
            all_facilities.append(facility)
        time.sleep(1)
    
    # 保存结果
    df = pd.DataFrame(all_facilities)
    df.to_csv("shenzhen_facilities.csv", index=False, encoding="utf-8-sig")
    print(f"已保存 {len(df)} 条设施数据")


if __name__ == "__main__":
    main()
'''

OSM_DIRECT_DOWNLOAD = '''
# OSM Shapefile直接下载 - 使用geofabrik数据
import requests
import zipfile
import os
import geopandas as gpd
from shapely.geometry import shape
import json

def download_osm_shp(region="guangdong", save_dir="./osm_data"):
    """
    从Geofabrik下载OSM SHP数据
    
    参数:
        region: 区域名 (如 "guangdong", "china")
        save_dir: 保存目录
    """
    os.makedirs(save_dir, exist_ok=True)
    
    base_url = "https://download.geofabrik.de/asia/china"
    zip_path = os.path.join(save_dir, f"{region}.zip")
    extract_dir = os.path.join(save_dir, region)
    
    # 下载
    url = f"{base_url}/{region}-latest-free.shp.zip"
    print(f"正在下载: {url}")
    
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get("content-length", 0))
    
    downloaded = 0
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    print(f"\\r下载进度: {downloaded/total_size*100:.1f}%", end="")
    
    print("\\n下载完成!")
    
    # 解压
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)
    
    print(f"解压完成: {extract_dir}")
    return extract_dir

def filter_shenzhen(gdf):
    """
    从广东省数据中裁剪深圳市
    
    需要深圳市边界或使用坐标范围裁剪
    """
    # 深圳市坐标范围 (近似)
    shenzhen_bounds = {
        "minx": 113.75,
        "maxx": 114.62,
        "miny": 22.38,
        "maxy": 22.86
    }
    
    gdf_filtered = gdf.cx[
        shenzhen_bounds["minx"]:shenzhen_bounds["maxx"],
        shenzhen_bounds["miny"]:shenzhen_bounds["maxy"]
    ]
    
    return gdf_filtered

# 使用示例
if __name__ == "__main__":
    # 下载广东省数据
    extract_dir = download_osm_shp("guangdong")
    
    # 读取POI数据
    poi_path = os.path.join(extract_dir, "gis_osm_pois_a_free.shp")
    if os.path.exists(poi_path):
        gdf_poi = gpd.read_file(poi_path)
        gdf_shenzhen = filter_shenzhen(gdf_poi)
        gdf_shenzhen.to_file("shenzhen_poi.shp")
        print(f"深圳市POI: {len(gdf_shenzhen)} 条")
    
    # 读取道路数据
    road_path = os.path.join(extract_dir, "gis_osm_roads_free.shp")
    if os.path.exists(road_path):
        gdf_road = gpd.read_file(road_path)
        gdf_shenzhen_road = filter_shenzhen(gdf_road)
        gdf_shenzhen_road.to_file("shenzhen_roads.shp")
        print(f"深圳市道路: {len(gdf_shenzhen_road)} 条")
'''

# 主程序 - 数据获取向导
def main():
    print(DATA_SOURCES)
    
    print("\n" + "="*70)
    print("数据获取向导")
    print("="*70)
    
    print("""
请选择数据获取方案:

【方案A: 纯开源方案 - 推荐用于学术研究】
  优点: 完全免费，数据质量较好
  步骤:
    1. 运行OSM数据下载脚本 (download_osm.py)
    2. 申请高德API免费Key
    3. 运行API数据采集脚本 (collect_amap.py)
    4. 处理合并数据

【方案B: 开源+商业数据 - 推荐用于完整研究】
  优点: 数据更完整，包含运营时间
  步骤:
    1. 从CSDN数据商购买深圳POI数据
    2. 配合OSM路网数据
    3. 运行数据处理脚本

【方案C: 全API方案 - 适合小范围研究】
  优点: 数据最新
  缺点: 需处理API限额
  步骤:
    1. 申请高德/百度API Key
    2. 运行API采集脚本
    3. 分批采集数据

【推荐研究流程】
  1. 先用OSM获取基础地理数据 (免费)
  2. 再用API获取营业时间数据 (免费额度)
  3. 合并处理进行分析
    """)

if __name__ == "__main__":
    main()
