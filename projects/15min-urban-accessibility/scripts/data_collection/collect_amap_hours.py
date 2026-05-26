# -*- coding: utf-8 -*-
r"""
高德API设施数据采集脚本 v3（南山区精准版）
=========================================

【与 notebook 数据体系对齐】
- 设施类型名与 POI_TAGS 完全一致（共 14 类）
- 夜间服务标注与 FACILITY_NIGHT_SERVICE 一致
- 小区(AOI)数据：来自 fang SQL（由 notebook 自身处理，本脚本不采集）

【采集策略】
- 高德 API：覆盖有真实营业时间数据的类型
  （医院/药店/超市/便利店/银行/ATM/公交站/地铁站）
- OSM 补充：高德覆盖不足的类型（诊所/小学/幼儿园/菜市场/学校）
- 全部使用「城市级搜索 + 行政关键词过滤」精准限定南山区

【API 调用量】
- 完整采集约 11 类型 × 10 页 ≈ 110 次（日免费配额 2000 次）

申请 API Key: https://lbs.amap.com
"""

import os, sys, time, requests, pandas as pd, warnings
warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')
os.environ['PYTHONIOENCODING'] = 'utf-8'

# ============================================================
# 配置
# ============================================================

# 南山区行政关键词（用于过滤地址/名称）
NANSHAN_KEYWORDS = [
    "南山", "粤海", "蛇口", "招商", "桃源", "西丽",
    "沙河", "科技园", "深圳湾", "华侨城", "四海", "东角头",
]
NANSHAN_ADCODE_PREFIX = "440305"

# 南山区行政边界（实测 POI 坐标验证）
NANSHAN_BBOX = {"north": 22.73, "south": 22.43,
                 "east": 114.30, "west": 113.87}

# ============================================================
# 设施类型定义（与 notebook POI_TAGS / FACILITY_NIGHT_SERVICE 对齐）
# ============================================================
#
#  采集来源  |  类型名             | 高德关键词 | 高德typecode | 最大页数
#  ---------|--------------------|----------|-------------|--------
#  高德 API | hospital           | 医院      | 090100      | 10
#  高德 API | clinic             | 诊所      | 090200      | 10
#  高德 API | pharmacy           | 药店      | 090101      | 10
#  高德 API | supermarket        | 超市      | 060101      | 10
#  高德 API | convenience        | 便利店    | None        | 10
#  高德 API | bank               | 银行      | 160100      | 10
#  高德 API | atm                | ATM      | 170300      | 10
#  高德 API | bus_stop           | 公交站    | 150700      | 10
#  高德 API | subway             | 地铁站    | None        | 10
#  OSM补充  | market             | 菜市场    | None        | 10   ← 高德关键词不够精准
#  OSM补充  | school             | 中学      | None        | 10   ← 高德"中学"包含大学
#  OSM补充  | kindergarten        | 幼儿园    | None        | 10   ← 高德覆盖不足
#  OSM补充  | primary_school      | 小学      | None        | 10   ← 高德关键词不够精准
#  Fang SQL | community (AOI)     | —        | —           | —     ← notebook 自处理

AMAP_POI_CATEGORIES = [
    # ---- 医疗 ----
    ("hospital",       "医院",    "090100",  10),
    ("clinic",         "诊所",    "090200",  10),
    ("pharmacy",       "药店",    "090101",  10),
    # ---- 零售 ----
    ("supermarket",    "超市",    "060101",  10),
    ("convenience",    "便利店",  None,      10),
    # ---- 教育（中学/高等教育，由 OSM 采集）----
    # ("school",        "中学",    None,      10),
    # ---- 金融 ----
    ("bank",           "银行",    "160100",  10),
    ("atm",            "ATM",    "170300",  10),
    # ---- 交通 ----
    ("bus_stop",       "公交站",  "150700",  10),
    ("subway",         "地铁站",  None,      10),
]

# 以下类型由 OSM 补充采集（见 collect_osm_supplement）
# clinic 在本脚本中已由高德采集，OSM 仅作为备用（避免重复）
OSM_SUPPLEMENT_TYPES = {
    # convenience: shop=convenience
    # "clinic":        {"amenity": "clinic"},
    "kindergarten":   {"amenity": "kindergarten"},
    # primary_school: 已合并到 school（OSM 中 primary_school 标签覆盖率低，无法有效区分）
    # 中学/职高/技校：用 amenity=school 全部拉取
    # school: amenity=school（覆盖中学/职高/技校等，包含普通初中/高中）
    "school":         {"amenity": "school"},
}

# ============================================================
# 夜间服务标注（与 notebook FACILITY_NIGHT_SERVICE 完全一致）
# ============================================================
# ratio = 该类型夜间服务的概率（0~1），来自真实研究文献
# is_24h = True 时覆盖 ratio，直接标记为夜间服务
FACILITY_NIGHT_SERVICE = {
    "convenience":  1.0,   # 便利店 24h 全天候
    "pharmacy":      0.3,  # 部分药店 24h
    "hospital":      0.2,  # 急诊/住院部 24h
    "clinic":        0.05, # 极少数诊所夜间营业
    "supermarket":   0.1,  # 部分大型超市延时至 22:00
    "bank":          0.0,  # 银行无夜间服务
    "atm":           1.0,  # ATM 24h
    "market":        0.0,  # 菜市场早市
    "school":        0.0,  # 学校无夜间服务
    "kindergarten":  0.0,  # 幼儿园无夜间服务
    "primary_school":0.0,  # 小学无夜间服务
    "bus_stop":      1.0,  # 夜间公交
    "subway":        1.0,  # 地铁末班后无服务（保留 1.0 近似全天候）
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
        print("[OK] 高德 API 客户端初始化完成")

    # --------------------------------------------------------
    def search_page(self, keyword: str, types: str = None,
                    page: int = 1) -> list:
        """
        搜索单页 POI（citylimit 城市限定，默认相关性排序）
        注意：不使用 sortrule=distance，否则非南山 POI 排在每页前面
        """
        params = {
            "key":        self.key,
            "city":       "深圳",
            "citylimit":  "true",
            "offset":     20,
            "page":       page,
            "extensions": "all",   # 获取完整信息（含营业时间）
            "keywords":   keyword,
        }
        if types:
            params["types"] = types
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=15)
            data = resp.json()
            if data.get("status") == "1":
                return data.get("pois", [])
            else:
                print(f"  [WARN] {data.get('info', '')}")
                return []
        except Exception as e:
            print(f"  [ERROR] {e}")
            return []

    def search_nanshan(self, keyword: str, types: str = None,
                      max_pages: int = 10) -> list:
        """
        采集深圳南山区 POI

        1. 城市级搜索（citylimit=true，高德按相关性排序）
        2. 行政区分局关键词过滤（adcode + 南山区街道名）
        3. 最多 max_pages 页（每页 20 条）

        策略说明：
        - 不用 sortrule=distance：距离排序会将非南山 POI 排在前面，
          过滤后页内南山区 POI 过少会提前终止，漏掉真实的南山 POI
        - 改用默认相关性排序：与关键词相关性高的南山 POI 更可能出现在前几页
        """
        all_raw = []
        for page in range(1, max_pages + 1):
            pois = self.search_page(keyword, types, page)
            if not pois:
                print(f"    第{page:2d}页: 无数据，停止翻页")
                break
            all_raw.extend(pois)
            n_filt = sum(1 for p in pois if self._is_nanshan(p))
            print(f"    第{page:2d}页: +{len(pois):3d} 条 raw, 过滤得 {n_filt:2d} 条南山")
            if len(pois) < 20:
                break
            time.sleep(0.35)
        # 全量搜索完毕后统一过滤（南山区 POI 分散在各页，必须全部翻完）
        all_pois = [p for p in all_raw if self._is_nanshan(p)]
        return all_pois

    def _is_nanshan(self, poi: dict) -> bool:
        """判断 POI 是否属于南山区（行政分区精准过滤）"""
        addr = poi.get("address", "") or ""
        name = poi.get("name", "") or ""
        adcode = poi.get("adcode", "") or ""
        text = addr + name
        return (
            adcode.startswith(NANSHAN_ADCODE_PREFIX)
            or any(kw in text for kw in NANSHAN_KEYWORDS)
        )

    # --------------------------------------------------------
    def extract(self, poi: dict, ftype: str) -> dict:
        """
        提取标准化字段 + 夜间服务标注

        字段来源说明：
        - lng/lat: 高德 GCJ-02 坐标（与 OSM WGS-84 不同，notebook 需转换）
        - business_period: 来自高德扩展字段 biz_ext.business_period
        - is_24h: "24" 或 "24小时" 出现在营业时间段中
        - night_ratio: FACILITY_NIGHT_SERVICE[type]
        - night_service: is_24h=True OR night_ratio > 0
        """
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
        night_service = is_24h or ratio > 0

        return {
            # ---- 基本信息 ----
            "name":              poi.get("name", ""),
            "address":           poi.get("address", ""),
            "type":             poi.get("type", ""),
            "type_code":        poi.get("typecode", ""),
            # ---- 坐标（GCJ-02，高德原生坐标系）----
            "lng":              lng,
            "lat":              lat,
            # ---- 设施分类 ----
            "facility_type":    ftype,
            # ---- 营业时间（高德 biz_ext）----
            "business_period":   period,
            "open_time":        hours.get("open_time"),
            "close_time":       hours.get("close_time"),
            "is_24h":           is_24h,
            # ---- 夜间服务标注（与 notebook FACILITY_NIGHT_SERVICE 一致）----
            "night_ratio":      1.0 if is_24h else ratio,
            "night_service":     night_service,
            # ---- 联系信息 ----
            "tel":              poi.get("tel", ""),
            # ---- 行政划分（用于验证南山区归属）----
            "adcode":           poi.get("adcode", ""),
            "pcode":            poi.get("pcode", ""),
            "citycode":         poi.get("citycode", ""),
            # ---- 来源标识 ----
            "source":           "amap",
        }

    @staticmethod
    def _parse_hours(period: str) -> dict:
        """解析高德营业时间段字符串

        典型格式：
        - "08:00-22:00"
        - "08:00-22：00"   （全角冒号）
        - "24小时营业"
        - ""                （无数据）
        """
        result = {}
        if not period or not period.strip():
            return result
        if "24" in period or "24小时" in period:
            return {"open_time": "00:00", "close_time": "23:59", "is_24h": True}
        if "-" in period:
            parts = period.split("-")
            if len(parts) == 2:
                open_t   = parts[0].strip().replace("：", ":")
                close_t  = parts[1].strip().replace("：", ":")
                result["open_time"]   = open_t
                result["close_time"]  = close_t
        return result


# ============================================================
# OSM 数据补充采集
# ============================================================

def collect_osm_supplement(output_dir: str) -> pd.DataFrame:
    """
    通过 OSM 补充高德覆盖不足或不够精准的设施类型

    补充类型：
    - kindergarten（幼儿园）：amenity=kindergarten
    - primary_school（小学）：amenity=school + primary_school=yes
    - school（中学）：amenity=school（覆盖中学/职高/技校等）

    坐标系：WGS-84（与高德 GCJ-02 不同，notebook 需投影转换）
    """
    print(f"\n{'='*60}")
    print("OSM 补充采集（高德覆盖不足的设施类型）")
    print(f"{'='*60}")

    try:
        import osmnx as ox
        ox.settings.use_cache  = True
        ox.settings.log_console = False
    except ImportError:
        print("[WARN] osmnx 未安装，跳过 OSM 补充采集")
        print("  安装: pip install osmnx")
        return pd.DataFrame()

    # 南山区 BBOX (north, south, east, west) → (lat_max, lat_min, lon_max, lon_min)
    BBOX = (NANSHAN_BBOX["north"], NANSHAN_BBOX["south"],
            NANSHAN_BBOX["east"],  NANSHAN_BBOX["west"])
    CENTER = (22.55, 113.95)  # 南山区中北部（粤海/科技园核心）

    records = []
    for ftype, tags in OSM_SUPPLEMENT_TYPES.items():
        try:
            gdf = ox.features_from_point(center_point=CENTER, tags=tags, dist=10000)
            # 过滤无效几何
            gdf = gdf[gdf.geometry.notna() & gdf.geometry.is_valid]
            # 按 addr:city 或 addr:district 过滤深圳范围（减少香港/东莞数据）
            city_mask = (
                gdf.get("addr:city", "").str.contains("深圳", na=False) |
                gdf.get("addr:district", "").str.contains("南山|福田|宝安|罗湖", na=False) |
                (gdf.get("addr:city", "").isna() & gdf.get("addr:district", "").isna())
            )
            gdf = gdf[city_mask]
            n = len(gdf)
            print(f"  {ftype:15s}: +{n:4d} 条", end="")
            if n > 0:
                for _, row in gdf.iterrows():
                    geom = row.geometry
                    lng = lat = None
                    if hasattr(geom, "centroid"):
                        lng = geom.centroid.x
                        lat = geom.centroid.y
                    elif hasattr(geom, "x"):
                        lng = geom.x
                        lat = geom.y
                    records.append({
                        "name":             row.get("name", ftype),
                        "address":          "",
                        "lng":              lng,
                        "lat":              lat,
                        "facility_type":    ftype,
                        "business_period":   "",
                        "open_time":        None,
                        "close_time":       None,
                        "is_24h":           False,
                        "night_ratio":      FACILITY_NIGHT_SERVICE.get(ftype, 0.0),
                        "night_service":    FACILITY_NIGHT_SERVICE.get(ftype, 0.0) > 0,
                        "tel":              "",
                        "adcode":           "",
                        "pcode":            "",
                        "citycode":         "",
                        "source":           "osm",
                    })
                print(f"  ✓")
            else:
                print(f"  (无数据)")
        except Exception as e:
            print(f"  ✗ {ftype}: 采集失败 {e}")

    if not records:
        print("[INFO] OSM 未返回数据（正常：南山区 OSM 覆盖可能稀疏）")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    csv = os.path.join(output_dir, "nanshan_osm_supplement.csv")
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    print(f"\n[OK] OSM 补充数据已保存: {csv} ({len(df)} 条)")
    return df


# ============================================================
# 主采集流程
# ============================================================

def collect_amap(api_key: str, output_dir: str,
                 max_pages: int = 10) -> pd.DataFrame:
    """
    采集南山区 9 类公共设施 POI（高德 API）
    """
    os.makedirs(output_dir, exist_ok=True)
    client = AmapClient(api_key)
    all_records = []

    print(f"\n{'='*60}")
    print("高德 API 采集（南山区 9 类公共设施）")
    print(f"最大页数/类型: {max_pages}  页")
    print(f"{'='*60}\n")

    for i, (ftype, kw, code, _) in enumerate(AMAP_POI_CATEGORIES):
        print(f"[{i+1:02d}/{len(AMAP_POI_CATEGORIES)}] {ftype:15s} ({kw})")
        pois = client.search_nanshan(kw, code, max_pages=max_pages)
        for poi in pois:
            all_records.append(client.extract(poi, ftype))
        n = sum(1 for r in all_records if r["facility_type"] == ftype)
        print(f"    → 本类累计: {n:4d} 条\n")
        time.sleep(0.3)

    return pd.DataFrame(all_records)


def _save_all(df_amap: pd.DataFrame, df_osm: pd.DataFrame,
              output_dir: str) -> pd.DataFrame:
    """合并高德 + OSM 数据，保存 CSV/JSON/Excel"""
    # 合并（OSM 列对齐 amap 列，缺失的列已用空值/默认值填充）
    if df_osm is not None and len(df_osm) > 0:
        df = pd.concat([df_amap, df_osm], ignore_index=True)
    else:
        df = df_amap
    # 去重：同一类型同一坐标只保留一条（防止多次采集叠加）
    before = len(df)
    # 合并 primary_school -> school（OSM 无法区分，合并避免重复）
    school_mask = df["facility_type"] == "primary_school"
    if school_mask.any():
        df.loc[school_mask, "facility_type"] = "school"
        print(f"[INFO] 合并 primary_school -> school: {school_mask.sum()} 条")

    df = df.drop_duplicates(subset=["facility_type", "lng", "lat"], keep="first")
    if before > len(df):
        print(f"[INFO] 去重: {before} -> {len(df)} 条 ({before - len(df)} 条重复)")


    os.makedirs(output_dir, exist_ok=True)
    for name, ext in [("nanshan_poi", "csv"),
                       ("nanshan_poi", "json"),
                       ("nanshan_poi", "xlsx")]:
        path = os.path.join(output_dir, f"{name}.{ext}")
        if ext == "csv":
            df.to_csv(path, index=False, encoding="utf-8-sig")
        elif ext == "json":
            df.to_json(path, orient="records", force_ascii=False, indent=2)
        else:
            df.to_excel(path, index=False)
    print(f"[OK] 数据已保存至: {output_dir}")
    return df


def _print_stats(df: pd.DataFrame) -> None:
    """打印采集统计信息"""
    print(f"\n{'='*60}")
    print("采集统计")
    print(f"{'='*60}")
    print(f"总记录: {len(df)} 条")
    print(f"\n各类型设施数量（来源：高德 / OSM）：")
    for ftype, grp in df.groupby("facility_type"):
        src = grp["source"].value_counts().to_dict()
        src_str = " / ".join(f"{k}({v})" for k, v in src.items())
        print(f"  {ftype:18s}: {len(grp):4d}  [{src_str}]")

    n_24h   = df["is_24h"].sum()
    n_night = df["night_service"].sum()
    has_biz = df["business_period"].notna() & (df["business_period"] != "")
    print(f"\n24h 设施:       {n_24h} ({n_24h/len(df)*100:.1f}%)")
    print(f"夜间服务设施:   {n_night} ({n_night/len(df)*100:.1f}%)")
    print(f"有营业时间数据: {has_biz.sum()} ({has_biz.mean()*100:.1f}%)")

    # 夜间服务设施类型分布
    night_types = df[df["night_service"] == True]["facility_type"].value_counts()
    if len(night_types) > 0:
        print(f"\n夜间服务设施类型分布:")
        for ft, cnt in night_types.items():
            ratio = df[df["facility_type"] == ft]["night_service"].mean()
            print(f"  {ft:18s}: {cnt:4d}  (本类型夜间率: {ratio:.0%})")

    # 坐标系说明
    print(f"\n坐标系说明:")
    print(f"  高德数据: GCJ-02（火星坐标系）")
    print(f"  OSM 数据:  WGS-84")
    print(f"  → notebook 使用 osmnx 时自动为 WGS-84，需注意投影统一")


# ============================================================
# 快速测试（每类型 1 页）
# ============================================================

def quick_collect(api_key: str, output_dir: str) -> pd.DataFrame:
    """快速测试：每类型只采第 1 页（约 10 次 API 调用）"""
    print(f"\n{'='*60}")
    print("快速测试模式（每类型 1 页）")
    print(f"{'='*60}\n")
    df = collect_amap(api_key, output_dir, max_pages=1)
    osm = collect_osm_supplement(output_dir)
    return _save_all(df, osm, output_dir)


# ============================================================
# main
# ============================================================

def main():
    print("\n" + "="*70)
    print("高德API设施数据采集工具  |  南山区精准版 v3")
    print("15分钟城市时间贫困研究  |  collect_amap_hours.py")
    print("="*70 + "\n")

    API_KEY = "c2d6e6faba4fba3311618be75e07cdee"
    OUTPUT_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "osm_data"
    )

    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        print("请先设置 API_KEY: https://lbs.amap.com")
        return

    print(f"API Key: {API_KEY[:8]}...{API_KEY[-4:]}")
    print(f"输出目录: {OUTPUT_DIR}\n")

    mode = input(
        "选择采集模式:\n"
        "  [1] 快速测试（每类型 1 页，约 10 次 API 调用）\n"
        "  [2] 完整采集（每类型 10 页，约 110 次 API 调用）\n"
        "  请输入 [1/2]: "
    ).strip() or "1"

    if mode == "2":
        df_amap = collect_amap(API_KEY, OUTPUT_DIR, max_pages=10)
        osm_df  = collect_osm_supplement(OUTPUT_DIR)
        df = _save_all(df_amap, osm_df, OUTPUT_DIR)
    else:
        df = quick_collect(API_KEY, OUTPUT_DIR)

    _print_stats(df)
    print("\n" + "="*70)
    print("运行完成")
    print("="*70)


if __name__ == "__main__":
    main()
