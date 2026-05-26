# -*- coding: utf-8 -*-
"""诊断：高德 district 参数实际行为"""
import sys, requests, time
sys.stdout.reconfigure(encoding='utf-8')

KEY = "c2d6e6faba4fba3311618be75e07cdee"
URL = "https://restapi.amap.com/v3/place/text"
HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36"}

def search(**kw):
    r = requests.get(URL, params=kw, headers=HEADERS, timeout=15)
    d = r.json()
    return d

print("=== 测试 1: citylimit + district ===")
d = search(key=KEY, city="深圳市", citylimit="true",
           district="南山区", keywords="医院", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}, info={d.get('info')}")
if d.get("pois"):
    print(f"  第1条: {d['pois'][0].get('name')} | adcode={d['pois'][0].get('adcode')}")
print()

print("=== 测试 2: 去掉 district，保留 citylimit ===")
d = search(key=KEY, city="深圳市", citylimit="true",
           keywords="医院", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}")
pois = d.get("pois", [])
ns = [p for p in pois if p.get("adcode","").startswith("440305")]
print(f"  raw={len(pois)}, 南山区={len(ns)}")
for p in pois[:3]:
    print(f"  {p.get('name')} | adcode={p.get('adcode')}")
print()

print("=== 测试 3: 不限城市，不限区域，搜「南山区医院」 ===")
d = search(key=KEY, keywords="南山区 医院", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}")
pois = d.get("pois", [])
ns = [p for p in pois if p.get("adcode","").startswith("440305")]
print(f"  raw={len(pois)}, 南山区={len(ns)}")
print()

print("=== 测试 4: 不限城市，搜「南山医院」 ===")
d = search(key=KEY, keywords="南山医院", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}")
pois = d.get("pois", [])
ns = [p for p in pois if p.get("adcode","").startswith("440305")]
print(f"  raw={len(pois)}, 南山区={len(ns)}")
print()

print("=== 测试 5: district=深圳, keywords=南山区 ===")
d = search(key=KEY, city="深圳市", district="深圳市",
           keywords="南山区", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}, info={d.get('info')}")
print()

print("=== 测试 6: district=440305 (adcode) ===")
d = search(key=KEY, city="深圳市", citylimit="true",
           district="440305", keywords="医院", extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}, info={d.get('info')}")
pois = d.get("pois", [])
if pois:
    print(f"  第1条: {pois[0].get('name')} | adcode={pois[0].get('adcode')}")
print()

print("=== 测试 7: polygon 参数（南山区 WKT）===")
# 南山区多边形近似坐标
POLYGON = "113.798,22.406;114.020,22.406;114.020,22.646;113.798,22.646;113.798,22.406"
d = search(key=KEY, city="深圳市", citylimit="true",
           keywords="医院", types="090100",
           polygon=POLYGON, extensions="all", offset=25, page=1)
print(f"status={d.get('status')}, count={d.get('count')}, info={d.get('info')}")
pois = d.get("pois", [])
ns = [p for p in pois if p.get("adcode","").startswith("440305")]
print(f"  raw={len(pois)}, 南山区={len(ns)}")
for p in pois[:3]:
    print(f"  {p.get('name')} | adcode={p.get('adcode')}")
