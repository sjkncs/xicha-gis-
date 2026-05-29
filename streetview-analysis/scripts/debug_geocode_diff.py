"""对比两种调用的差异"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
import full_pipeline
import requests

# 直接抄 amap_regeocode 的逻辑
lng, lat = 113.8500636, 22.5669725
key = "dd10c4dea07d700b83ae9c09cbaf0aad"

gcj_lng, gcj_lat = full_pipeline.wgs84_to_gcj02(lng, lat)
print(f"GCJ02: {gcj_lng},{gcj_lat}")

params = {
    "key": key,
    "location": f"{gcj_lng},{gcj_lat}",
    "radius": 200,
    "extensions": "base",
    "batch": "false",
    "output": "json",
}

print(f"URL: https://restapi.amap.com/v3/geocode/regeo")
print(f"Params: {params}")

# 直接调
r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=10)
print(f"\nStatus: {r.status_code}")
print(f"Text: {r.text[:200]}")

data = r.json()
print(f"data type: {type(data)}")
print(f"data: {data}")

# 用 amap_regeocode 函数
print("\n--- amap_regeocode result ---")
result = full_pipeline.amap_regeocode(lng, lat, key)
print(f"Result: {result}")
