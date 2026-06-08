"""调试full_pipeline模块"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")

# 直接打印模块里的函数
import full_pipeline
print(f"Module loaded: {full_pipeline.__file__}")
print(f"AMAP_KEY: {full_pipeline.AMAP_KEY[:8]}...")
print(f"wgs84_to_gcj02: {full_pipeline.wgs84_to_gcj02}")

lng, lat = 113.9263685, 22.5129279
gcj_lng, gcj_lat = full_pipeline.wgs84_to_gcj02(lng, lat)
print(f"GCJ02: {gcj_lng}, {gcj_lat}")

# 直接调API
import requests
params = {
    "key": full_pipeline.AMAP_KEY,
    "location": f"{gcj_lng},{gcj_lat}",
    "radius": 200,
    "extensions": "base",
    "output": "json",
}
r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=10)
print(f"Response: {r.text[:300]}")
data = r.json()
print(f"Status: {data.get('status')}, Info: {data.get('info')}")
