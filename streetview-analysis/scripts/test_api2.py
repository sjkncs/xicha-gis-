"""调试高德API"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import json

# 测试两个key
keys = ["c2d6e6faba4fba3311618be75e07cdee", "dd10c4dea07d700b83ae9c09cbaf0aad"]
lng, lat = 113.9263685, 22.5129279
# 先WGS84转GCJ02
import math
PI = 3.14159265358979324
A = 6378245.0
EE = 0.00669342162296594323

def _transform_lat(x, y):
    ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0 / 3.0
    ret += (20.0*math.sin(y*PI) + 40.0*math.sin(y/3.0*PI)) * 2.0 / 3.0
    ret += (160.0*math.sin(y/12.0*PI) + 320.0*math.sin(y*PI/30.0)) * 2.0 / 3.0
    return ret

def _transform_lng(x, y):
    ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI)) * 2.0 / 3.0
    ret += (20.0*math.sin(x*PI) + 40.0*math.sin(x/3.0*PI)) * 2.0 / 3.0
    ret += (150.0*math.sin(x/12.0*PI) + 300.0*math.sin(x/30.0*PI)) * 2.0 / 3.0
    return ret

def wgs84_to_gcj02(lng, lat):
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / (((A * (1 - EE)) / (magic * sqrtmagic)) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat

gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
print(f"GCJ02: {gcj_lng}, {gcj_lat}")

for key in keys:
    url = "https://restapi.amap.com/v3/geocode/regeo"
    params = {
        "key": key,
        "location": f"{gcj_lng},{gcj_lat}",
        "radius": 200,
        "extensions": "base",
        "output": "json",
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"\nKey {key[:8]}...: status={r.status_code}")
        print(f"  Response: {r.text[:300]}")
        data = r.json()
        print(f"  status field: {data.get('status')}")
        print(f"  info: {data.get('info')}")
        if data.get("regeocodes"):
            rc = data["regeocodes"][0]
            ac = rc.get("addressComponent", {})
            print(f"  district: {ac.get('district')}")
            print(f"  township: {ac.get('township')}")
            print(f"  neighborhood: {ac.get('neighborhood')}")
            print(f"  formatted: {rc.get('formatted_address', '')[:60]}")
    except Exception as e:
        print(f"Key {key[:8]}... Error: {e}")
