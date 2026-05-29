"""快速测试高德逆地理编码API"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
from full_pipeline import amap_regeocode, AMAP_KEY

# 测试坐标（n201中的几个点）
test_coords = [
    (113.9263685, 22.5129279),   # Village, 登良路
    (113.93115580923161, 22.524743775467694),  # High-Rise, 滨海大道
    (113.8500636, 22.5669725),   # Open/Other
]

for lng, lat in test_coords:
    print(f"\n测试: {lng}, {lat}")
    result = amap_regeocode(lng, lat)
    if result:
        print(f"  地址: {result.get('formatted_address', '')}")
        print(f"  区: {result.get('district', '')}")
        print(f"  街道: {result.get('township', '')}")
        print(f"  社区: {result.get('neighborhood', '')}")
        print(f"  路: {result.get('street', '')} {result.get('number', '')}")
    else:
        print("  失败!")
