# -*- coding: utf-8 -*-
"""
最终整合脚本 v6（审慎版）
将 Ground Truth（69,422条）与 V5 API 夜间服务标注合并
夜间服务标注策略：
  1. 优先使用 V5 API 直接标注（最可靠）
  2. 仅对 V5 标注为夜间服务(True) 的同类设施类型做正向推断
  3. 其他未标注设施按经验保守判断（部分夜间营业类型）
"""
import pandas as pd, numpy as np, sys, os, warnings
from scipy.spatial import cKDTree

sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT = BASE + r"\osm_data"

# ============================================================
# 1. 加载数据
# ============================================================
gaode = pd.read_csv(BASE + r"\osm_data\nanshan_poi_gaode.csv", low_memory=False)
v5 = pd.read_csv(BASE + r"\osm_data\nanshan_poi_v5.csv", low_memory=False)
print(f"Ground Truth: {len(gaode)} 条")
print(f"V5 API: {len(v5)} 条")

# ============================================================
# 2. 列名标准化
# ============================================================
gaode.rename(columns={"lon": "gcj_lon", "lat": "gcj_lat"}, inplace=True)
gaode["night_service"] = None
gaode["v5_matched"] = False
v5.rename(columns={"lng": "gcj_lon"}, inplace=True)

# ============================================================
# 3. 设施类型（Ground Truth 关键词匹配）
# ============================================================
TYPE_PATTERNS = [
    ("商务写字楼", ["写字楼", "商务大厦", "产业园区", "科技园", "工业园"]),
    ("购物服务",   ["商场", "超市", "便利店", "专卖店", "购物中心", "商业街"]),
    ("餐饮服务",   ["餐厅", "饭店", "小吃", "快餐", "咖啡", "茶", "酒吧",
                  "火锅", "烧烤", "美食", "食府", "食堂"]),
    ("医疗保健",   ["医院", "诊所", "药店", "门诊", "卫生站", "医疗", "保健"]),
    ("教育培训",   ["学校", "培训", "教育", "幼儿园", "小学", "中学",
                  "大学", "学院", "党校", "少年宫"]),
    ("交通设施",   ["地铁", "地铁站", "公交", "停车场", "站点", "客运",
                  "站场", "驿站", "停车"]),
    ("公共设施",   ["公共厕所", "ATM", "银行", "自助", "警务", "消防"]),
    ("休闲娱乐",   ["影院", "Ktv", "KTV", "ktv", "网吧", "健身", "游乐",
                  "公园", "广场", "体育", "棋牌", "美容", "SPA", "足浴"]),
    ("住宿服务",   ["酒店", "宾馆", "旅馆", "民宿", "招待所", "公寓"]),
    ("生活服务",   ["洗衣", "理发", "摄影", "快递", "物业", "维修", "中介"]),
    ("公司企业",   ["公司", "工厂", "企业", "集团", "实业"]),
    ("政府机构",   ["政府", "街道", "社区", "派出", "服务中心"]),
]

def resolve_ftype(name, cat1="", cat2=""):
    if pd.isna(name): return "其他"
    for ftype, kws in TYPE_PATTERNS:
        for kw in kws:
            if kw in str(name):
                return ftype
    for c in filter(lambda x: not pd.isna(x), [str(cat1), str(cat2)]):
        s = str(c)
        if any(k in s for k in ["商场", "超市", "便利店", "购物"]): return "购物服务"
        if any(k in s for k in ["餐饮", "美食", "小吃", "快餐"]): return "餐饮服务"
        if any(k in s for k in ["医疗", "药店", "医院"]): return "医疗保健"
        if any(k in s for k in ["学校", "培训", "教育"]): return "教育培训"
        if any(k in s for k in ["交通", "站点", "公交", "停车"]): return "交通设施"
        if any(k in s for k in ["公共", "银行", "ATM"]): return "公共设施"
        if any(k in s for k in ["娱乐", "运动", "健身", "公园"]): return "休闲娱乐"
        if any(k in s for k in ["酒店", "宾馆", "住宿"]): return "住宿服务"
        if any(k in s for k in ["公司", "工厂", "企业"]): return "公司企业"
    return "其他"

gaode["facility_type"] = gaode.apply(
    lambda r: resolve_ftype(r["name"], r.get("category1"), r.get("category2")), axis=1)

# ============================================================
# 4. V5 设施类型英文转中文
# ============================================================
V5_TYPE_MAP = {
    "bus_stop": "交通设施", "kindergarten": "教育培训", "school": "教育培训",
    "gym": "休闲娱乐", "subway": "交通设施", "supermarket": "购物服务",
    "bar": "餐饮服务", "park": "休闲娱乐", "clinic": "医疗保健",
    "hospital": "医疗保健", "restaurant": "餐饮服务", "bank": "公共设施",
    "pharmacy": "医疗保健", "cinema": "休闲娱乐", "hotel": "住宿服务",
    "cafe": "餐饮服务", "convenience": "购物服务", "parking": "交通设施",
    "toilet": "公共设施",
}
v5["facility_type_v5"] = v5["facility_type"].apply(
    lambda x: V5_TYPE_MAP.get(str(x).strip().lower(), "其他") if not pd.isna(x) else "其他")

# ============================================================
# 5. 空间匹配（KDTree）
# ============================================================
gaode_valid = gaode.dropna(subset=["gcj_lon", "gcj_lat"]).copy()
gaode_valid["_lon"] = gaode_valid["gcj_lon"].round(6)
gaode_valid["_lat"] = gaode_valid["gcj_lat"].round(6)
gaode_pts = gaode_valid[["_lon", "_lat"]].values
tree = cKDTree(gaode_pts)

v5_valid = v5.dropna(subset=["gcj_lon", "lat"]).copy()
v5_valid["_lon"] = v5_valid["gcj_lon"].round(6)
v5_valid["_lat"] = v5_valid["lat"].round(6)
v5_pts = v5_valid[["_lon", "_lat"]].values
distances, indices = tree.query(v5_pts)

THRESHOLD = 0.001
mask = distances <= THRESHOLD
matched_gt_pos = indices[mask]
matched_v5_pos = np.where(mask)[0]
matched_dists = distances[mask]

print(f"\n空间匹配: {len(matched_gt_pos)} / {len(v5_valid)} ({len(matched_gt_pos)/len(v5_valid)*100:.1f}%)")
print(f"  中位距离: {np.median(matched_dists)*111000:.0f}m  最大: {np.max(matched_dists)*111000:.0f}m")

# ============================================================
# 6. 将 V5 标注写入 Ground Truth
# ============================================================
updated_night = 0
for i in range(len(matched_gt_pos)):
    gt_idx_in_valid = matched_gt_pos[i]
    v5_idx = matched_v5_pos[i]
    gaode_row = gaode_valid.index[gt_idx_in_valid]
    v5_row = v5_valid.iloc[v5_idx]

    gaode.at[gaode_row, "v5_matched"] = True
    ns = v5_row.get("night_service")
    if pd.notna(ns):
        gaode.at[gaode_row, "night_service"] = ns
        if str(ns).lower() == "true":
            updated_night += 1

print(f"已映射 {updated_night} 条 V5 夜间服务标注到 Ground Truth")

# ============================================================
# 7. 夜间服务最终推断（保守策略）
# ============================================================
# 直接标注（V5 匹配）: night_service == True
# 负向推断: V5 标注为 False -> 同类型均视为无夜间服务
# 正向推断: 仅对明确夜间类设施做保守正向推断
V5_NIGHT_TYPES = {"交通设施", "公共设施", "住宿服务", "休闲娱乐"}
V5_NO_NIGHT_TYPES = {"教育培训", "政府机构", "商务写字楼", "公司企业", "医疗保健"}
# 购物服务和餐饮服务：V5 中既有 True 也有 False，不做统一推断

def is_night_true(ns):
    if pd.isna(ns): return None
    s = str(ns).lower()
    if s == "true": return True
    if s == "false": return False
    return None

def infer_night_service(row):
    # 优先用直接标注
    direct = is_night_true(row.get("night_service"))
    if direct is True: return True
    if direct is False: return False

    # 设施类型推断
    ft = str(row.get("facility_type", "其他"))
    if ft in V5_NIGHT_TYPES:
        return True  # 交通设施、公共设施、住宿、休闲 夜间一般营业
    if ft in V5_NO_NIGHT_TYPES:
        return False  # 学校、政府、写字楼、公司、医疗 夜间一般不营业
    # 购物/餐饮/其他 不做统一推断，返回 None
    return False  # 保守：默认无夜间服务

gaode["night_service_final"] = gaode.apply(infer_night_service, axis=1)

# ============================================================
# 8. 统计
# ============================================================
total = len(gaode)
night_direct = ((gaode["night_service"]==True) | (gaode["night_service"].astype(str).str.lower()=="true")).sum()
night_final = gaode["night_service_final"].sum()

print(f"\n{'='*55}")
print(f"【整合后 Nanshan POI 统计报告】")
print(f"{'='*55}")
print(f"  总 POI 数量:         {total:,}")
print(f"  V5 直接标注夜间:     {night_direct} ({night_direct/total*100:.1f}%)")
print(f"  含夜间推断夜间总计:  {night_final} ({night_final/total*100:.1f}%)")

print(f"\n【各设施类型夜间服务覆盖】")
print(f"{'设施类型':<12} {'总数':>7} {'夜间':>8} {'占比':>7} {'来源':>10}")
print("-" * 55)
vc = gaode["facility_type"].value_counts()
for ftype, count in vc.items():
    ns = gaode[gaode["facility_type"]==ftype]["night_service_final"].sum()
    v5_n = ((gaode[gaode["facility_type"]==ftype]["night_service"]==True) |
            (gaode[gaode["facility_type"]==ftype]["night_service"].astype(str).str.lower()=="true")).sum()
    source = "直接+V5推断" if ftype in V5_NIGHT_TYPES else ("直接" if v5_n > 0 else "默认无")
    print(f"{ftype:<12} {count:>7,} {ns:>8,} {ns/count*100:>6.1f}%  {source:>10}")

print(f"\n【夜间服务 POI 分布】")
night_df = gaode[gaode["night_service_final"]==True]
print(night_df["facility_type"].value_counts().to_string())

print(f"\n【整合数据质量摘要】")
print(f"  V5 API 成功匹配:     {gaode['v5_matched'].sum():,} 条")
print(f"  未匹配 (纯推断):     {(~gaode['v5_matched']).sum():,} 条")
print(f"  夜间服务 POI 总计:   {night_final:,} 条")

# ============================================================
# 9. 保存
# ============================================================
out_csv = OUT + r"\nanshan_poi_integrated.csv"
out_json = OUT + r"\nanshan_poi_integrated.json"
gaode.to_csv(out_csv, index=False, encoding="utf-8")
gaode.to_json(out_json, orient="records", force_ascii=False, indent=2)
print(f"\n已保存: {out_csv}")
print(f"已保存: {out_json}")
print(f"字段: {gaode.columns.tolist()}")
