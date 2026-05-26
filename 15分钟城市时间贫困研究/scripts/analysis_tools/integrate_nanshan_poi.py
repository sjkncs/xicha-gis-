# -*- coding: utf-8 -*-
"""最终整合：使用高德 ground truth（69,422条）作为南山区 POI 基础数据"""
import pandas as pd, sys, os
sys.stdout.reconfigure(encoding='utf-8')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# ============================================================
# 1. 读取高德 ground truth（全南山区 POI）
# ============================================================
gaode = pd.read_csv(os.path.join(BASE, "osm_data", "nanshan_poi_gaode.csv"), low_memory=False)
print(f"高德南山区 ground truth: {len(gaode)} 条")

# ============================================================
# 2. 读取 v5 采集的营业时间数据（1,412条）
# ============================================================
v5_path = os.path.join(BASE, "osm_data", "nanshan_poi_v5.csv")
v5 = pd.read_csv(v5_path, low_memory=False) if os.path.exists(v5_path) else pd.DataFrame()
print(f"v5 营业时间采集: {len(v5)} 条" if len(v5) else "v5 数据: 未找到")

# ============================================================
# 3. 建立 POI 名称 → 营业时间的映射
# ============================================================
if len(v5) > 0:
    # 使用 (name, lng, lat) 组合作为键（避免同名POI误匹配）
    hours_map = {}
    for _, row in v5.dropna(subset=["lng", "lat"]).iterrows():
        key = (str(row["name"]).strip(), round(float(row["lng"]), 6), round(float(row["lat"]), 6))
        hours_map[key] = {
            "business_period": row.get("business_period", ""),
            "open_time": row.get("open_time"),
            "close_time": row.get("close_time"),
            "is_24h": row.get("is_24h", False),
            "night_ratio": row.get("night_ratio", 0.0),
            "night_service": row.get("night_service", False),
            "source": row.get("source", ""),
            "facility_type": row.get("facility_type", ""),
        }
    print(f"营业时间映射表: {len(hours_map)} 个 POI 有营业时间")

    # 合并营业时间
    def merge_hours(row):
        key = (str(row["name"]).strip(), round(float(row["lon"]), 6), round(float(row["lat"]), 6))
        if key in hours_map:
            h = hours_map[key]
            return pd.Series({
                "business_period": h["business_period"],
                "open_time": h["open_time"],
                "close_time": h["close_time"],
                "is_24h": h["is_24h"],
                "night_ratio": h["night_ratio"],
                "night_service": h["night_service"],
                "source_amap": h["source"],
                "facility_type": h["facility_type"],
            })
        return pd.Series()

    hours_cols = gaode.apply(merge_hours, axis=1)
    for col in hours_cols.columns:
        gaode[col] = hours_cols[col]
else:
    gaode["business_period"] = None
    gaode["open_time"] = None
    gaode["close_time"] = None
    gaode["is_24h"] = False
    gaode["night_ratio"] = 0.0
    gaode["night_service"] = False
    gaode["source_amap"] = "gaode_only"
    gaode["facility_type"] = None

# ============================================================
# 4. 建立 POI 中类 → facility_type 的映射（与 notebook 对齐）
# ============================================================
CAT2FTYPE = {
    # 医疗
    "综合医院": "hospital", "专科医院": "hospital", "急救中心": "hospital",
    "诊所": "clinic", "卫生室": "clinic",
    "医药销售": "pharmacy", "药店": "pharmacy",
    # 零售
    "超市": "supermarket",
    "便利店": "convenience",
    "市场": "market", "农贸市场": "market", "菜市场": "market",
    # 金融
    "银行": "bank",
    "ATM": "atm",
    # 交通
    "公交站": "bus_stop", "公交线路": "bus_stop",
    "地铁站": "subway", "地铁": "subway",
    # 教育
    "中学": "school", "九年一贯制学校": "school",
    "幼儿园": "kindergarten",
    "小学": "school",
    "高等教育": "school", "培训单位": "school",
    # 休闲
    "公园": "park", "旅游景点": "park",
    "健身中心": "gym", "运动健身": "gym", "体育健身": "gym",
    "电影院": "cinema",
    "中国菜": "restaurant", "小吃快餐": "restaurant",
    "餐饮服务": "restaurant", "外国菜": "restaurant",
    "咖啡": "restaurant", "茶座": "restaurant",
    "蛋糕甜品店": "restaurant",
    "酒吧": "bar",
    # AOI 类型（小区）
    "住宅区": "community", "商住两用楼宇": "community",
}

def map_cat2ftype(row):
    if pd.notna(row.get("facility_type")) and str(row.get("facility_type", "")) not in ("", "None"):
        return row["facility_type"]
    cat2 = str(row.get("category2", "")).strip()
    if cat2 in CAT2FTYPE:
        return CAT2FTYPE[cat2]
    cat1 = str(row.get("category1", "")).strip()
    if cat1 == "医疗保健":
        if "销售" in cat2: return "pharmacy"
        if "医院" in cat2: return "hospital"
        return "clinic"
    if cat1 == "购物消费":
        if "便利" in cat2: return "convenience"
        if "超市" in cat2: return "supermarket"
        if "市场" in cat2: return "market"
        return "retail"
    if cat1 == "交通设施":
        if "公交" in cat2: return "bus_stop"
        if "地铁" in cat2: return "subway"
        return "transport"
    if cat1 == "餐饮美食":
        return "restaurant"
    if cat1 == "科教文化":
        if "幼儿" in cat2: return "kindergarten"
        return "school"
    if cat1 == "运动健身":
        return "gym"
    if cat1 == "酒店住宿":
        return "hotel"
    if cat1 == "金融":
        if "ATM" in cat2: return "atm"
        return "bank"
    if cat1 == "旅游景点":
        return "park"
    return None

gaode["facility_type_mapped"] = gaode.apply(map_cat2ftype, axis=1)

# ============================================================
# 5. 统计
# ============================================================
print(f"\n=== 南山区 POI 整合结果 ===")
print(f"总记录: {len(gaode)} 条")

print(f"\n各 facility_type 数量:")
ftype_stats = gaode.groupby("facility_type_mapped").agg(
    total=("name", "count"),
).sort_values("total", ascending=False)
has_period = gaode["business_period"].notna() & (gaode["business_period"] != "")
has_night = gaode.get("night_service", pd.Series(False, index=gaode.index))
if has_night.dtype == object:
    has_night = gaode["night_service"].map(lambda x: bool(x) if pd.notna(x) else False)
print(ftype_stats.to_string())

print(f"\n高德原始营业时间（有 biz_ext）:")
print(f"  有营业时间: {has_period.sum()} 条 ({has_period.mean()*100:.1f}%)")
print(f"  夜间服务: {has_night.sum()} 条 ({has_night.mean()*100:.1f}%)")

# ============================================================
# 6. 输出
# ============================================================
out_cols = ["lon", "lat", "name", "category1", "category2",
            "facility_type_mapped", "address",
            "business_period", "open_time", "close_time",
            "is_24h", "night_ratio", "night_service",
            "source_amap"]
# 保留高德原始列
existing = [c for c in out_cols if c in gaode.columns]
df_out = gaode[existing].copy()
df_out = df_out.rename(columns={"facility_type_mapped": "facility_type"})

out_csv = os.path.join(BASE, "osm_data", "nanshan_poi_final.csv")
df_out.to_csv(out_csv, index=False, encoding="utf-8-sig")
print(f"\n已保存: {out_csv} ({len(df_out)} 条)")

out_json = os.path.join(BASE, "osm_data", "nanshan_poi_final.json")
df_out.to_json(out_json, orient="records", force_ascii=False, indent=2)
print(f"已保存: {out_json}")

# ============================================================
# 7. 与 notebook 的 POI_TAGS 对齐检查
# ============================================================
print(f"\n=== 与 notebook POI_TAGS 对齐检查 ===")
NOTEBOOK_TAGS = ["hospital", "clinic", "pharmacy", "supermarket",
                 "convenience", "market", "bank", "atm",
                 "bus_stop", "subway", "school", "kindergarten",
                 "park", "gym", "cinema", "restaurant", "bar",
                 "community", "retail", "transport"]

mapped = set(df_out["facility_type"].dropna().unique())
for tag in NOTEBOOK_TAGS:
    cnt = len(df_out[df_out["facility_type"] == tag])
    status = "✓" if cnt > 0 else "✗ 缺失"
    print(f"  {tag:15s}: {cnt:6d} 条 {status}")
