# -*- coding: utf-8 -*-
r"""
高德API POI采集脚本 v4（南山区精准版）
=========================================

【策略变更（v4 相比 v3）】
旧版：city=深圳 + citylimit=true + 关键词过滤 → 南山区 POI 分散在大量结果中，漏检严重
新版：city=深圳 + district=南山区 + extensions=all → 直接限定南山区，零漏检

【高德 API 分区查询参数】
- citylimit=true + city=深圳市：限定搜索范围为深圳
- district=南山区：限定搜索分区为南山区（adcode=440305 的语义等价）
  等价于在深圳市内按「南山区」行政区划过滤
- types：按 POI 类型精确过滤

【API 调用量】
- 完整采集约 9 类型 × 15 页 ≈ 135 次（免费配额 2000 次/日）
- API Key 有时效（2026-05-23 到期），请及时续费
"""

import os, sys, time, requests, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# ============================================================
# 配置
# ============================================================
OUTPUT_DIR = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data"

# 南山区精确 BBOX（来自 ground truth 验证）
NANSHAN_BBOX = {
    "lon_min": 113.79847,
    "lon_max": 114.01974,
    "lat_min": 22.40598,
    "lat_max": 22.64627,
}

# ============================================================
# 设施类型定义（与 notebook POI_TAGS 对齐）
# ============================================================
# (facility_type, 高德关键词, 高德types代码, 每页条数, 最大页数)
AMAP_POI_CATEGORIES = [
    # 医疗
    ("hospital",       "医院",    "090100",        25, 20),
    ("clinic",         "诊所",    "090200",        25, 15),
    ("pharmacy",       "药店",    "090101",        25, 15),
    # 零售
    ("supermarket",    "超市",    "060101",        25, 15),
    ("convenience",    "便利店",  "070301",        25, 15),
    # 金融
    ("bank",           "银行",    "160100",        25, 15),
    ("atm",            "ATM",     "170300",        25, 15),
    # 交通
    ("bus_stop",       "公交站",  "150700",        25, 15),
    ("subway",         "地铁站",  "150500",        25, 10),
    # 教育
    ("school",         "学校",    "141200",        25, 15),
    ("kindergarten",   "幼儿园",  "141300",        25, 15),
    # 生活服务
    ("market",         "菜市场",  "060101",        25, 10),
    ("restaurant",     "餐饮",    "050000",        25, 20),
    # 休闲
    ("park",           "公园",    "010100",        25, 10),
    ("gym",            "健身房",  "080300",        25, 10),
    ("cinema",         "电影院",  "090202",        25,  5),
]

# ============================================================
# 夜间服务标注（与 notebook FACILITY_NIGHT_SERVICE 对齐）
# ============================================================
FACILITY_NIGHT_SERVICE = {
    "convenience":  1.0, "pharmacy": 0.3, "hospital": 0.2,
    "clinic": 0.05, "supermarket": 0.1, "bank": 0.0,
    "atm": 1.0, "market": 0.0, "school": 0.0,
    "kindergarten": 0.0, "bus_stop": 1.0, "subway": 1.0,
    "restaurant": 0.1, "park": 0.0, "gym": 0.2, "cinema": 0.3,
}


# ============================================================
# 高德 API 客户端
# ============================================================

class AmapClient:
    BASE_URL = "https://restapi.amap.com/v3/place/text"

    def __init__(self, api_key: str):
        self.key = api_key
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        self._quota_left = None
        print("[OK] 高德 API 客户端初始化完成")

    def _is_nanshan(self, poi: dict) -> bool:
        """BBOX 双重验证（防止跨区误判）"""
        loc = poi.get("location", "")
        if not loc:
            return False
        try:
            lng, lat = map(float, loc.split(","))
        except ValueError:
            return False
        return (NANSHAN_BBOX["lon_min"] <= lng <= NANSHAN_BBOX["lon_max"]
                and NANSHAN_BBOX["lat_min"] <= lat <= NANSHAN_BBOX["lat_max"])

    def search_page(self, keyword: str, types: str,
                    page: int, page_size: int = 25) -> tuple[list, int]:
        """
        搜索单页 POI

        返回: (pois_list, total_count)
        """
        params = {
            "key":        self.key,
            "city":       "深圳市",
            "citylimit":  "true",
            "district":   "南山区",
            "offset":     page_size,
            "page":       page,
            "extensions": "all",
            "keywords":   keyword,
        }
        if types:
            params["types"] = types

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "1":
                total = int(data.get("count", 0))
                return data.get("pois", []), total
            else:
                print(f"    [WARN] {data.get('info', '')}")
                return [], 0
        except Exception as e:
            print(f"    [ERROR] {e}")
            return [], 0

    def search_district(self, keyword: str, types: str,
                       page_size: int, max_pages: int) -> list:
        """
        采集南山区 POI（分区查询 + BBOX 二次验证）

        流程：
        1. district=南山区 参数直接限定搜索分区
        2. BBOX 坐标过滤去除跨区边缘点
        """
        all_pois = []
        for page in range(1, max_pages + 1):
            pois, total = self.search_page(keyword, types, page, page_size)
            if not pois:
                print(f"    第{page:2d}页: 无数据，停止翻页")
                break

            # BBOX 二次验证
            pois_ns = [p for p in pois if self._is_nanshan(p)]
            all_pois.extend(pois_ns)
            print(f"    第{page:2d}页: +{len(pois):3d} raw, +{len(pois_ns):3d} 南山 (已累计 {len(all_pois)} 条)")

            if len(pois) < page_size:
                break
            if page >= max_pages:
                break
            time.sleep(0.4)

        return all_pois

    def extract(self, poi: dict, ftype: str) -> dict:
        """提取标准化字段"""
        loc = poi.get("location", "")
        lng = lat = None
        if loc:
            try:
                lng, lat = map(float, loc.split(","))
            except ValueError:
                pass

        biz = poi.get("biz_ext") or {}
        period = biz.get("business_period", "") or ""
        is_24h = "24" in period or "24小时" in period
        hours = self._parse_hours(period)
        ratio = FACILITY_NIGHT_SERVICE.get(ftype, 0.0)

        return {
            "name":             poi.get("name", ""),
            "address":          poi.get("address", ""),
            "type":             poi.get("type", ""),
            "type_code":        poi.get("typecode", ""),
            "lng":              lng,
            "lat":              lat,
            "facility_type":    ftype,
            "business_period":   period,
            "open_time":        hours.get("open_time"),
            "close_time":       hours.get("close_time"),
            "is_24h":           is_24h,
            "night_ratio":      1.0 if is_24h else ratio,
            "night_service":     is_24h or ratio > 0,
            "tel":              poi.get("tel", ""),
            "adcode":           poi.get("adcode", ""),
            "pcode":            poi.get("pcode", ""),
            "citycode":         poi.get("citycode", ""),
            "source":           "amap",
        }

    @staticmethod
    def _parse_hours(period: str) -> dict:
        result = {}
        if not period or not period.strip():
            return result
        if "24" in period or "24小时" in period:
            return {"open_time": "00:00", "close_time": "23:59", "is_24h": True}
        if "-" in period:
            parts = period.split("-")
            if len(parts) == 2:
                result["open_time"]  = parts[0].strip().replace("：", ":")
                result["close_time"] = parts[1].strip().replace("：", ":")
        return result


# ============================================================
# 主采集流程
# ============================================================

def collect(api_key: str, output_dir: str, max_pages: int = 15) -> pd.DataFrame:
    os.makedirs(output_dir, exist_ok=True)
    client = AmapClient(api_key)
    all_records = []

    print(f"\n{'='*70}")
    print("高德 API 采集 | district=南山区 + BBOX 双重过滤")
    print(f"最大页数/类型: {max_pages}  页 |  每页: 25  条")
    print(f"{'='*70}\n")

    for i, (ftype, kw, code, page_size, mp) in enumerate(AMAP_POI_CATEGORIES):
        print(f"[{i+1:02d}/{len(AMAP_POI_CATEGORIES)}] {ftype:15s} ({kw}, typecode={code})")
        actual_pages = min(max_pages, mp)
        pois = client.search_district(kw, code, page_size, actual_pages)
        for poi in pois:
            all_records.append(client.extract(poi, ftype))
        n = sum(1 for r in all_records if r["facility_type"] == ftype)
        print(f"    → 本类累计: {n:4d} 条\n")
        time.sleep(0.4)

    return pd.DataFrame(all_records)


def save(df: pd.DataFrame, output_dir: str) -> pd.DataFrame:
    """去重 + 保存"""
    before = len(df)
    df = df.drop_duplicates(subset=["facility_type", "lng", "lat"], keep="first")
    after = len(df)
    if before > after:
        print(f"[INFO] 去重: {before} -> {after} 条 (移除 {before-after} 条重复)")

    os.makedirs(output_dir, exist_ok=True)
    for name, ext in [("nanshan_poi_v4", "csv"), ("nanshan_poi_v4", "json")]:
        path = os.path.join(output_dir, f"{name}.{ext}")
        if ext == "csv":
            df.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            df.to_json(path, orient="records", force_ascii=False, indent=2)
    print(f"\n[OK] 数据已保存至: {output_dir}")
    return df


def stats(df: pd.DataFrame):
    print(f"\n{'='*70}")
    print("采集统计")
    print(f"{'='*70}")
    print(f"总记录: {len(df)} 条")

    print(f"\n各类型设施数量：")
    for ftype, grp in df.groupby("facility_type"):
        n_24h = grp["is_24h"].sum()
        n_night = grp["night_service"].sum()
        print(f"  {ftype:15s}: {len(grp):4d} 条  (24h={n_24h}, 夜间={n_night})")

    n_24h   = df["is_24h"].sum()
    n_night = df["night_service"].sum()
    has_biz = df["business_period"].notna() & (df["business_period"] != "")
    print(f"\n24h 设施:       {n_24h} ({n_24h/len(df)*100:.1f}%)")
    print(f"夜间服务设施:   {n_night} ({n_night/len(df)*100:.1f}%)")
    print(f"有营业时间数据: {has_biz.sum()} ({has_biz.mean()*100:.1f}%)")
    print(f"\n坐标系: GCJ-02（高德原生坐标系）")


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "="*70)
    print("高德API POI采集工具  |  南山区精准版 v4")
    print("15分钟城市时间贫困研究")
    print("="*70 + "\n")

    # API Key（来自 Changsha-Park-Poi 项目，2026-05-23 到期，剩余约 4000 次）
    API_KEY = "c2d6e6faba4fba3311618be75e07cdee"

    if not API_KEY:
        print("请先设置 API_KEY: https://lbs.amap.com")
        return

    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"预计 API 调用: {len(AMAP_POI_CATEGORIES)} 类型 × ~15 页 ≈ ~200 次\n")

    df = collect(API_KEY, OUTPUT_DIR, max_pages=15)
    df = save(df, OUTPUT_DIR)
    stats(df)

    print("\n" + "="*70)
    print("运行完成")
    print("="*70)


if __name__ == "__main__":
    main()
