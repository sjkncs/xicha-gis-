# -*- coding: utf-8 -*-
"""诊断：高德 district 查询各类型南山区 POI 总量"""
import sys, requests, time
sys.stdout.reconfigure(encoding='utf-8')

KEY = "c2d6e6faba4fba3311618be75e07cdee"
HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36"}
NANSHAN_ADCODE = "440305"

BBOX = (113.79847, 114.01974, 22.40598, 22.64627)

def is_ns(poi):
    ad = poi.get("adcode", "") or ""
    loc = poi.get("location", "") or ""
    if ad.startswith(NANSHAN_ADCODE):
        return True
    if loc:
        try:
            parts = loc.split(",")
            lng = float(parts[0])
            lat = float(parts[1])
            if BBOX[0] <= lng <= BBOX[1] and BBOX[2] <= lat <= BBOX[3]:
                return True
        except Exception:
            pass
    return False

def search(**kw):
    r = requests.get("https://restapi.amap.com/v3/place/text", params=kw, headers=HEADERS, timeout=15)
    return r.json()

test_types = [
    ("hospital",    "090100"),
    ("clinic",      "090200"),
    ("pharmacy",    "090101"),
    ("supermarket", "060101"),
    ("convenience", "070301"),
    ("bank",        "160100"),
    ("atm",         "170300"),
    ("bus_stop",    "150700"),
    ("subway",      "150500"),
    ("school",      "141200"),
    ("kindergarten","141300"),
    ("park",        "010100"),
    ("gym",         "080300"),
    ("restaurant",  "050000"),
]

print("=" * 60)
print("测试1: 三种 district 参数对比")
print("=" * 60)

for ftype, code in test_types:
    # district=南山区
    d1 = search(key=KEY, city="深圳市", citylimit="true",
                 district="南山区", types=code, extensions="all", offset=25, page=1)
    count1 = int(d1.get("count", 0))
    ns1 = sum(1 for p in d1.get("pois", []) if is_ns(p))

    # district=440305
    d2 = search(key=KEY, city="深圳市", citylimit="true",
                 district="440305", types=code, extensions="all", offset=25, page=1)
    count2 = int(d2.get("count", 0))
    ns2 = sum(1 for p in d2.get("pois", []) if is_ns(p))

    # 无district（对照组）
    d3 = search(key=KEY, city="深圳市", citylimit="true",
                 types=code, extensions="all", offset=25, page=1)
    ns3 = sum(1 for p in d3.get("pois", []) if is_ns(p))

    print(f"  {ftype:15s} | dist=南山区: cnt={count1} ns={ns1}  | dist=440305: cnt={count2} ns={ns2}  | citylimit only: ns={ns3}")
    time.sleep(0.3)

print()
print("=" * 60)
print("测试2: district=南山区，逐类型翻页到底，统计南山区 POI 总量")
print("=" * 60)

for ftype, code in test_types:
    total_ns = 0
    for page in range(1, 20):
        d = search(key=KEY, city="深圳市", citylimit="true",
                   district="南山区", types=code, extensions="all", offset=25, page=page)
        pois = d.get("pois", [])
        if not pois:
            break
        ns = sum(1 for p in pois if is_ns(p))
        total_ns += ns
        if len(pois) < 25:
            break
        time.sleep(0.25)
    print(f"  {ftype:15s}: district=南山区 南山区 POI 总量 = {total_ns}")
