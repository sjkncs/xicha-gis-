# -*- coding: utf-8 -*-
"""
高德 POI 行政区数据查询（南山区）
=====================================

高德 POI 搜索 API 有 500 条/类型 硬上限，无法获取完整数据。
解决方案：使用高德「行政区数据查询」API
  https://restapi.amap.com/v3/config/district

该 API 专门用于获取某行政区划内的 POI，不受 500 条限制。
可以按子区域（街道/镇）拆分查询。
"""
import sys, requests, time, json
sys.stdout.reconfigure(encoding='utf-8')

KEY = "c2d6e6faba4fba6fba3311618be75e07cdee"  # 请替换为有效 Key

def district_search(keywords, subdistrict=3, offset=100, page=1):
    """高德行政区划 POI 查询"""
    url = "https://restapi.amap.com/v3/config/district"
    params = {
        "key": key,
        "keywords": keywords,
        "subdistrict": subdistrict,  # 0=不返回下级  1=街道级  2=社区级  3=详细
        "offset": offset,
        "page": page,
        "extensions": "all",  # 返回详细信息
    }
    r = requests.get(url, params=params, timeout=20)
    return r.json()

print("测试1: 获取南山区子区域（街道）列表")
d = district_search("南山区", subdistrict=1, offset=100, page=1)
print(f"status={d.get('status')}, info={d.get('info')}, count={d.get('count')}")
districts = d.get("districts", [])
if districts:
    print(f"南山区子区域: {len(districts)} 个")
    for sub in districts[:10]:
        print(f"  {sub.get('name')} | adcode={sub.get('adcode')} | cnt={sub.get('cnt')}")
        sub_districts = sub.get("districts", [])
        if sub_districts:
            print(f"    下级: {[s.get('name') for s in sub_districts[:5]]}")
