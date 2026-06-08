# -*- coding: utf-8 -*-
"""
百度街景全量采集 + 逆地理编码 + 标准化归档
Full Pipeline: Reverse Geocode + Baidu Street View Download + Archiving

流程:
  Step 1: 逆地理编码 — 高德API获取街道/社区
  Step 2: 全量下载 — 依次尝试 2022-2025 年
  Step 3: 标准化归档 — 南山区/街道/社区/形态/坐标

依赖: pip install requests Pillow
"""

import os, sys, json, time, random, math, csv, requests
from pathlib import Path

# ============================================================
# 基础路径
# ============================================================
SCRIPT_DIR  = Path(__file__).parent.resolve()
PROJ_DIR    = SCRIPT_DIR.parent / "projects" / "15min-urban-accessibility" / "data" / "streetview"
ARCHIVE_DIR  = SCRIPT_DIR / "baidu_streetview"
CACHE_DIR    = SCRIPT_DIR / ".pipeline_cache"
CACHE_DIR.mkdir(exist_ok=True)

N201_CSV = PROJ_DIR / "integrated_collection" / "samples" / "sample_points_n201.csv"

# API Keys
AMAP_KEY     = "dd10c4dea07d700b83ae9c09cbaf0aad"
TARGET_YEARS  = [2022, 2023, 2024, 2025]
DIRECTIONS    = [0, 90, 180, 270]
HEADING_LABELS = {0: "N", 90: "E", 180: "S", 270: "W"}

# ============================================================
# 坐标转换（与 StreeView_year.py 完全一致）
# ============================================================
PI      = 3.14159265358979324
A       = 6378245.0
EE      = 0.00669342162296594323
x_pi    = PI * 3000.0 / 180.0

LLBAND  = [75, 60, 45, 30, 15, 0]
LL2MC   = [
    [-0.0015702102444, 111320.7020616939, 1704480524535203, -10338987376042340,
     26112667856603880, -35149669176653700, 26595700718403920, -10725012454188240,
     1800819912950474, 82.5],
    [0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316,
     10774905663.51142, -15171875531.51559, 12053065338.62167, -5124939663.577472,
     913311935.9512032, 67.5],
    [0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662,
     79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821,
     8477230.501135234, 52.5],
    [0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245,
     992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312,
     144416.9293806241, 37.5],
    [-0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394,
     6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645,
     1405.483844121726, 22.5],
    [-0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718,
     0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284,
     0.37238884252424, 7.45],
]
MCBAND  = [12890594.86, 8362377.87, 5591021, 3481989.83, 1678043.12, 0]
MC2LL   = [
    [1.410526172116255e-8, 0.00000898305509648872, -1.9939833816331,
     200.9824383106796, -187.2403703815547, 91.6087516669843,
     -23.38765649603339, 2.57121317296198, -0.03801003308653, 17337981.2],
    [-7.435856389565537e-9, 0.000008983055097726239, -0.78625201886289,
     96.32687599759846, -1.85204757529826, -59.36935905485877,
     47.40033549296737, -16.50741931063887, 2.28786674699375, 10260144.86],
    [-3.030883460898826e-8, 0.00000898305509983578, 0.30071316287616,
     59.74293618442277, 7.357984074871, -25.38371002664745,
     13.45380521110908, -3.29883767235584, 0.32710905363475, 6856817.37],
    [-1.981981304930552e-8, 0.000008983055099779535, 0.03278182852591,
     40.31678527705744, 0.65659298677277, -4.44255534477492,
     0.85341911805263, 0.12923347998204, -0.04625736007561, 4482777.06],
    [3.09191371068437e-9, 0.000008983055096812155, 0.00006995724062,
     23.10934304144901, -0.00023663490511, -0.6321817810242,
     -0.00663494467273, 0.03430082397953, -0.00466043876332, 2555164.4],
    [2.890871144776878e-9, 0.000008983055095805407, -3.068298e-8,
     7.47137025468032, -0.00000353937994, -0.02145144861037,
     -0.00001234426596, 0.00010322952773, -0.00000323890364, 826088.5],
]


# --- BD 墨卡托坐标转换（来自 StreeView_year.py）---
def _out_of_china(lng, lat):
    if lng < 72.004 or lng > 137.8347:
        return True
    if lat < 0.8293 or lat > 55.8271:
        return True
    return False


def _transform_lat(lng, lat):
    ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 0.1 * lng * lat + 0.2 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * PI) + 40.0 * math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * PI) + 320.0 * math.sin(lat * PI / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(lng, lat):
    ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 0.1 * lng * lat + 0.1 * math.sqrt(math.fabs(lng))
    ret += (20.0 * math.sin(6.0 * lng * PI) + 20.0 * math.sin(2.0 * lng * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lng * PI) + 40.0 * math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lng / 12.0 * PI) + 300.0 * math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lng, lat):
    if _out_of_china(lng, lat):
        return lng, lat
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat


def gcj02_to_bd09(lng, lat):
    z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * x_pi)
    theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * x_pi)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def wgs84_to_bd09(lng, lat):
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
    return gcj02_to_bd09(gcj_lng, gcj_lat)


# --- BD 墨卡托转换（与 StreeView_year.py 一致）---
class _LLT:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _getRange(cC, cB, T):
    if cB is not None:
        cC = max(cC, cB)
    if T is not None:
        cC = min(cC, T)
    return cC


def _getLoop(cC, cB, T):
    while cC > T:
        cC -= T - cB
    while cC < cB:
        cC += T - cB
    return cC


def _convertor(cC, cD):
    if cC is None or cD is None:
        return None
    T = cD[0] + cD[1] * abs(cC.x)
    cB = abs(cC.y) / cD[9]
    cE = (cD[2] + cD[3] * cB + cD[4] * cB * cB + cD[5] * cB * cB * cB
           + cD[6] * cB * cB * cB * cB + cD[7] * cB * cB * cB * cB * cB
           + cD[8] * cB * cB * cB * cB * cB * cB)
    if cC.x < 0:
        T = T * -1
    if cC.y < 0:
        cE = cE * -1
    return [T, cE]


def _convertLL2MC(T):
    cD = None
    T.x = _getLoop(T.x, -180, 180)
    T.y = _getRange(T.y, -74, 74)
    cB = T
    for cC in range(0, len(LLBAND), 1):
        if cB.y >= LLBAND[cC]:
            cD = LL2MC[cC]
            break
    if cD is not None:
        for cC in range(len(LLBAND) - 1, -1, -1):
            if cB.y <= -LLBAND[cC]:
                cD = LL2MC[cC]
                break
    cE = _convertor(T, cD)
    return cE


def _bd09tomercator(lng, lat):
    baidut = _LLT(lng, lat)
    return _convertLL2MC(baidut)


def wgs84_to_bdmc(lng, lat):
    """WGS84 -> BD09 -> BD墨卡托（用于百度街景API）"""
    bd09_lng, bd09_lat = wgs84_to_bd09(lng, lat)
    mc = _bd09tomercator(bd09_lng, bd09_lat)
    return mc[0], mc[1]


# ============================================================
# 高德逆地理编码
# ============================================================
def amap_regeocode(lng_wgs, lat_wgs):
    gcj_lng, gcj_lat = wgs84_to_gcj02(lng_wgs, lat_wgs)
    params = {
        "key": AMAP_KEY,
        "location": f"{gcj_lng},{gcj_lat}",
        "radius": 200,
        "extensions": "base",
        "output": "json",
    }
    try:
        r = requests.get("https://restapi.amap.com/v3/geocode/regeo", params=params, timeout=10)
        data = r.json()
        if data.get("status") == "1" and data.get("regeocode"):
            rc = data["regeocode"]
            ac = rc.get("addressComponent", {})
            neigh = ac.get("neighborhood", {})
            neigh_name = neigh.get("name", "") if isinstance(neigh, dict) else ""
            return {
                "formatted_address": rc.get("formatted_address", ""),
                "district":     ac.get("district", ""),
                "township":     ac.get("township", ""),
                "neighborhood":  neigh_name,
                "street":        rc.get("streetNumber", {}).get("street", ""),
                "number":        rc.get("streetNumber", {}).get("number", ""),
            }
    except Exception:
        pass
    return None


def batch_regeocode_all(points, delay=0.15):
    results = []
    cache_file = CACHE_DIR / "regeocode_cache.json"
    cached = {}
    if cache_file.exists():
        try:
            with open(cache_file, encoding="utf-8") as f:
                cached = json.load(f)
        except Exception:
            pass

    total = len(points)
    for i, pt in enumerate(points):
        cache_key = f"{pt['lng']:.5f}_{pt['lat']:.5f}"
        if cache_key in cached:
            results.append(cached[cache_key])
        else:
            result = amap_regeocode(pt["lng"], pt["lat"])
            cached[cache_key] = result
            results.append(result)
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cached, f, ensure_ascii=False)
            except Exception:
                pass
            time.sleep(delay)
        if (i + 1) % 20 == 0:
            print(f"  逆编码: {i+1}/{total}")

    return results


# ============================================================
# 百度街景下载（与 StreeView_year.py 逻辑一致）
# ============================================================
UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]


def _headers():
    return {
        "User-Agent": random.choice(UA_LIST),
        "Referer": "https://map.baidu.com/",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }


def _date_str():
    return time.strftime("%Y%m%d", time.localtime())


def bd_sid(x, y):
    """用 BD 墨卡托坐标获取采样点 SID"""
    params = {
        "udt": _date_str(), "action": 0,
        "x": x, "y": y,
        "l": 18.367179030452565,
        "mode": "day",
        "t": int(time.time() * 1000),
        "fn": "jsonp1", "qt": "qsdata",
    }
    try:
        r = requests.get("https://mapsv0.bdimg.com/?", params=params, headers=_headers(), timeout=(5, 10))
        raw = r.content
        start = raw.find(b"(") + 1
        end = raw.rfind(b")")
        if start > 0 and end > start:
            j = json.loads(raw[start:end].decode("utf-8", errors="replace"))
            if j.get("result", {}).get("error") == 0:
                return j["content"]["id"]
    except Exception:
        pass
    return None


def sid_timeline(sid):
    """获取全景时间轴"""
    params = {
        "sid": sid, "pc": 1,
        "udt": _date_str(),
        "fn": "jsonp.p3991630", "qt": "sdata",
    }
    try:
        r = requests.get("https://mapsv0.bdimg.com/?", params=params, headers=_headers(), timeout=(3, 7))
        raw = r.content
        start = raw.find(b"(") + 1
        end = raw.rfind(b")")
        if start > 0 and end > start:
            j = json.loads(raw[start:end].decode("utf-8", errors="replace"))
            content = j.get("content", [])
            if content and isinstance(content, list):
                direction = float(content[0].get("MoveDir", 0))
                timeline = content[0].get("TimeLine", [])
                return direction, timeline
    except Exception:
        pass
    return 0.0, []


def _normalize_urban_form(uf):
    mapping = {
        "Village":        "Village-城中村",
        "High-End":       "HighEnd-高端社区",
        "Village Fringe": "VillageFringe-城中村边缘",
        "High-Rise":      "HighRise-高密度",
        "Mid-Rise":       "MidRise-中密度",
        "Low-Rise":       "LowRise-低密度",
        "Open/Other":     "OpenOther-开放其他",
    }
    return mapping.get(uf, uf or "OpenOther-开放其他")


def make_archive_path(addr_info, urban_form, lng, lat):
    district      = (addr_info.get("district", "南山区") if addr_info else "南山区")
    township      = (addr_info.get("township", "未知街道") or "未知街道")
    township      = township.replace("街道", "").replace("镇", "")
    neighborhood = (addr_info.get("neighborhood", "未知社区") or "未知社区")
    form_en       = _normalize_urban_form(urban_form)
    coord_dir     = f"{lng:.6f}_{lat:.6f}"
    return f"{district}/{township}/{neighborhood}/{form_en}/{coord_dir}"


def download_one_point(pt_info, urban_form, addr_info):
    """下载一个采样点的全部影像"""
    lng, lat = pt_info["lng"], pt_info["lat"]

    # 归档目录
    archive_base = ARCHIVE_DIR / make_archive_path(addr_info, urban_form, lng, lat)
    os.makedirs(archive_base, exist_ok=True)

    # 已有检查
    existing = list(archive_base.glob("*.jpg"))
    if len(existing) >= 4:
        print(f"  [已有{len(existing)}张] {lng:.6f},{lat:.6f}")
        return []

    # BD 墨卡托坐标
    bd_x, bd_y = wgs84_to_bdmc(lng, lat)

    # 获取 SID
    sid = bd_sid(bd_x, bd_y)
    if not sid:
        print(f"  [无SID] {lng:.6f},{lat:.6f}")
        return []

    # 获取时间轴
    direction, timeline = sid_timeline(sid)

    # 找目标年份的 timeid（从2022到2025依次找第一个有的）
    timeid_list = []
    for year in TARGET_YEARS:
        found = False
        for item in timeline:
            if int(item.get("Year", 0)) == year:
                timeid_list.append((year, item.get("ID")))
                found = True
                break
        if found:
            break

    if not timeid_list:
        print(f"  [无时间轴数据] {lng:.6f},{lat:.6f}")
        return []

    # 下载影像
    results = []
    for year, timeid in timeid_list:
        for head in DIRECTIONS:
            img_params = {
                "fovy": 90, "quality": 100,
                "panoid": timeid,
                "heading": (head + direction) % 360,
                "width": 512, "height": 512, "qt": "pr3d",
            }
            try:
                r = requests.get("https://mapsv0.bdimg.com/?", params=img_params,
                                 headers=_headers(), timeout=(3, 7))
                if r.content[:2] == b"\xff\xd8":
                    fname = f"{lng:.6f}_{lat:.6f}_{HEADING_LABELS[head]}_{year}.jpg"
                    fpath = archive_base / fname
                    with open(fpath, "wb") as f:
                        f.write(r.content)
                    results.append({
                        "success": True,
                        "lng": lng, "lat": lat,
                        "heading": head,
                        "heading_label": HEADING_LABELS[head],
                        "year": year, "size": len(r.content),
                        "archive_path": str(fpath),
                        "urban_form": urban_form,
                        "township": (addr_info.get("township", "") if addr_info else ""),
                        "community": (addr_info.get("neighborhood", "") if addr_info else ""),
                        "district": (addr_info.get("district", "南山区") if addr_info else "南山区"),
                        "road_fclass": pt_info.get("road_fclass", ""),
                        "road_name": pt_info.get("road_name", ""),
                    })
                    print(f"  [保存] {HEADING_LABELS[head]}/{year} {len(r.content)}B")
            except Exception:
                pass
            time.sleep(0.15)

    return results


# ============================================================
# 主流程
# ============================================================
def load_points():
    rows = []
    with open(N201_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                rows.append({
                    "idx": i,
                    "lng": float(row["lng"]),
                    "lat": float(row["lat"]),
                    "urban_form": row.get("urban_form", "Open/Other"),
                    "road_fclass": row.get("road_fclass", ""),
                    "road_name": row.get("road_name", "").strip(),
                })
            except Exception:
                pass
    return rows


def write_manifest(results, path):
    if not results:
        return
    fields = ["archive_path", "district", "township", "community",
              "urban_form", "road_fclass", "road_name",
              "lng", "lat", "heading", "heading_label", "year", "size"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            if r.get("success"):
                w.writerow({k: r.get(k, "") for k in fields})


def main():
    print("=" * 70)
    print("全量街景采集 — 逆地理编码 + 下载 + 归档")
    print("=" * 70)

    # Step 1: 加载
    points = load_points()
    print(f"\n[1/3] 采样点: {len(points)} 个")

    # Step 2: 逆地理编码
    print(f"\n[2/3] 逆地理编码（高德API）...")
    addr_results = batch_regeocode_all(points)
    ok = sum(1 for a in addr_results if a)
    print(f"  成功: {ok}/{len(addr_results)}")

    print("\n  地址示例（前5个）:")
    for i, a in enumerate(addr_results[:5]):
        if a:
            print(f"    [{i}] {a.get('district','')}{a.get('township','')}{a.get('neighborhood','')}")
            print(f"         {a.get('formatted_address','')[:55]}")

    # Step 3: 下载
    manifest_path = ARCHIVE_DIR / "manifest.csv"
    all_results = []
    done = skip = fail = 0

    print(f"\n[3/3] 下载街景影像...")
    for i, pt in enumerate(points):
        addr = addr_results[i]
        print(f"\n  [{i+1}/{len(points)}] {pt['lng']:.6f},{pt['lat']:.6f} "
              f"| {addr.get('township','') if addr else '?'} "
              f"| {pt['urban_form']}")

        res = download_one_point(pt, pt["urban_form"], addr)
        for r in res:
            all_results.append(r)
            if r.get("success"):
                done += 1

        # 进度保存
        if (i + 1) % 20 == 0:
            write_manifest(all_results, manifest_path)
            print(f"\n  ~~ 进度 {i+1}/{len(points)} | 成功{done} | manifest已保存")

    write_manifest(all_results, manifest_path)

    # 汇总
    from collections import Counter
    form_stats     = Counter(r["urban_form"] for r in all_results if r.get("success"))
    district_stats = Counter(r.get("district", "") for r in all_results if r.get("success"))
    township_stats  = Counter(r.get("township", "") for r in all_results if r.get("success"))

    print("\n" + "=" * 70)
    print("完成报告")
    print("=" * 70)
    print(f"  总点: {len(points)} | 成功: {done} 张")
    print(f"  manifest: {manifest_path}")
    print(f"  归档目录: {ARCHIVE_DIR}")
    if form_stats:
        print(f"\n  各形态:")
        for k, v in form_stats.most_common():
            print(f"    {k:25s}: {v}")
    if township_stats:
        print(f"\n  各街道:")
        for k, v in township_stats.most_common():
            print(f"    {(k or '未知'):15s}: {v}")
    print("=" * 70)


if __name__ == "__main__":
    main()
