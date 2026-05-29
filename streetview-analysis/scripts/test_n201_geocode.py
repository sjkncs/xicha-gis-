"""测试n201前几个坐标的逆地理编码"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")
import full_pipeline
import requests
import json

# 从 n201 加载前5个坐标
points = full_pipeline.load_sample_points()
print(f"Points: {[(p['lng'], p['lat']) for p in points[:5]]}")

# 直接调API
AMAP_KEY = "dd10c4dea07d700b83ae9c09cbaf0aad"
for pt in points[:5]:
    lng, lat = pt["lng"], pt["lat"]
    gcj_lng, gcj_lat = full_pipeline.wgs84_to_gcj02(lng, lat)
    params = {
        "key": AMAP_KEY,
        "location": f"{gcj_lng},{gcj_lat}",
        "radius": 200,
        "extensions": "base",
        "output": "json",
    }
    try:
        r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=10)
        print(f"\n{lng:.6f},{lat:.6f}")
        print(f"  GCJ02: {gcj_lng:.6f},{gcj_lat:.6f}")
        print(f"  Raw: {r.text[:200]}")
        data = r.json()
        if data.get("status") == "1" and data.get("regeocodes"):
            rc = data["regeocodes"][0]
            ac = rc.get("addressComponent", {})
            print(f"  OK: {ac.get('district')}{ac.get('township')}{ac.get('neighborhood')}")
        else:
            print(f"  FAIL: status={data.get('status')} info={data.get('info')}")
    except Exception as e:
        print(f"  ERROR: {e}")
