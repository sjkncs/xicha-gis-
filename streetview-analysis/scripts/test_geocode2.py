"""测试完整逆地理编码流程"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
from full_pipeline import amap_regeocode, AMAP_KEY

print(f"Using key: {AMAP_KEY[:8]}...")
print()

# 测试坐标（n201中的几个点）
test_coords = [
    (113.9263685, 22.5129279, "Village/登良路"),
    (113.93115580923161, 22.524743775467694, "High-Rise/滨海大道"),
    (113.8500636, 22.5669725, "Open/Other/绿道"),
    (113.89537357507588, 22.48178435162769, "Open/Other"),
    (113.93225246020573, 22.488924337955815, "Open/Other"),
]

for lng, lat, desc in test_coords:
    print(f"  {lng:.6f}, {lat:.6f}  ({desc})")
    result = amap_regeocode(lng, lat)
    if result:
        print(f"    区: {result.get('district', '')}")
        print(f"    街道: {result.get('township', '')}")
        print(f"    社区: {result.get('neighborhood', '')}")
        print(f"    路: {result.get('street', '')} {result.get('number', '')}")
        print(f"    完整地址: {result.get('formatted_address', '')[:60]}")
    else:
        print(f"    [失败]")
    print()
