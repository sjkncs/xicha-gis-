"""深入调试 amap_regeocode"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
import full_pipeline
import requests
import json

lng, lat = 113.8500636, 22.5669725
key = "dd10c4dea07d700b83ae9c09cbaf0aad"
gcj_lng, gcj_lat = full_pipeline.wgs84_to_gcj02(lng, lat)

params = {
    "key": key,
    "location": f"{gcj_lng},{gcj_lat}",
    "radius": 200,
    "extensions": "base",
    "batch": "false",
    "output": "json",
}

r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=10)
raw = r.content
print(f"Raw bytes length: {len(raw)}")
print(f"Raw: {raw[:100]}")

# 用标准 json.loads
data = json.loads(raw)
print(f"\njson.loads status: '{data.get('status')}' (type: {type(data.get('status'))})")
print(f"regeocodes in data: {'regeocodes' in data}")

# 用 r.json()
data2 = r.json()
print(f"\nr.json() status: '{data2.get('status')}' (type: {type(data2.get('status'))})")
print(f"regeocodes in data2: {'regeocodes' in data2}")

# 为什么 amap_regeocode 里的 if 判断失败？
print(f"\ndata.get('status') == '1': {data.get('status') == '1'}")
print(f"data.get('regeocodes'): {data.get('regeocodes')}")
print(f"bool check: {bool(data.get('regeocodes'))}")

# 直接运行 amap_regeocode 里的代码
def debug_regeocode(lng_wgs, lat_wgs, key):
    import requests
    import json
    gcj_lng, gcj_lat = full_pipeline.wgs84_to_gcj02(lng_wgs, lat_wgs)
    params = {
        "key": key,
        "location": f"{gcj_lng},{gcj_lat}",
        "radius": 200,
        "extensions": "base",
        "batch": "false",
        "output": "json",
    }
    try:
        r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=(5, 10))
        print(f"  HTTP status: {r.status_code}")
        print(f"  r.text[:100]: {r.text[:100]}")
        data = r.json()
        print(f"  data.get('status'): '{data.get('status')}'")
        print(f"  type: {type(data.get('status'))}")
        print(f"  data.get('regeocodes'): {bool(data.get('regeocodes'))}")
        print(f"  condition: {data.get('status') == '1' and data.get('regeocodes')}")
        if data.get("status") == "1" and data.get("regeocodes"):
            rj = data["regeocodes"][0]
            return rj.get("formatted_address", "")
    except Exception as e:
        print(f"  Exception: {e}")
    return None

print(f"\nResult: {debug_regeocode(lng, lat, key)}")
