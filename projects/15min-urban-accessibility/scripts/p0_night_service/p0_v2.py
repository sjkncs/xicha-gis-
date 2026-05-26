# -*- coding: utf-8 -*-
"""P0: Rebuild night_service_final with fine-grained inference"""
import pandas as pd, numpy as np, sys, io, time, json, ast
from scipy.spatial import cKDTree

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT  = BASE + r"\osm_data"

print("=" * 70)
print("P0: 重建夜间服务标注（精细化推断 v2）")
print("=" * 70)

# ── Load ──
gaode = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_gaode.csv", low_memory=False)
v5    = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_v5.csv",   low_memory=False)
print(f"Ground Truth: {len(gaode):,} 条")
print(f"V5 API:       {len(v5):,} 条")

# ── Columns ──
gaode.rename(columns={"lon": "gcj_lon", "lat": "gcj_lat"}, inplace=True)
gaode["night_service"] = None
gaode["v5_matched"] = False
v5.rename(columns={"lng": "gcj_lon"}, inplace=True)

# ── Type mapping ──
TP = [
    ("商务写字楼", ["写字楼","商务大厦","产业园区","科技园","工业园"]),
    ("购物服务",   ["商场","超市","便利店","专卖店","购物中心","商业街"]),
    ("餐饮服务",   ["餐厅","饭店","小吃","快餐","咖啡","茶","酒吧","火锅","烧烤","美食","食府","食堂"]),
    ("医疗保健",   ["医院","诊所","药店","门诊","卫生站","医疗","保健"]),
    ("教育培训",   ["学校","培训","教育","幼儿园","小学","中学","大学","学院","党校","少年宫"]),
    ("交通设施",   ["地铁","地铁站","公交","停车场","站点","客运","站场","驿站","停车"]),
    ("公共设施",   ["公共厕所","ATM","银行","自助","警务","消防"]),
    ("休闲娱乐",   ["影院","KTV","ktv","网吧","健身","游乐","公园","广场","体育","棋牌","美容","SPA","足浴"]),
    ("住宿服务",   ["酒店","宾馆","旅馆","民宿","招待所","公寓"]),
    ("生活服务",   ["洗衣","理发","摄影","快递","物业","维修","中介"]),
    ("公司企业",   ["公司","工厂","企业","集团","实业"]),
    ("政府机构",   ["政府","街道","社区","派出","服务中心"]),
]

def resolve_ftype(name, cat1="", cat2=""):
    if pd.isna(name): return "其他"
    for ftype, kws in TP:
        for kw in kws:
            if kw in str(name): return ftype
    for c in filter(lambda x: not pd.isna(x), [str(cat1), str(cat2)]):
        s = str(c)
        if any(k in s for k in ["商场","超市","便利店","购物"]): return "购物服务"
        if any(k in s for k in ["餐饮","美食","小吃","快餐"]): return "餐饮服务"
        if any(k in s for k in ["医疗","药店","医院"]): return "医疗保健"
        if any(k in s for k in ["学校","培训","教育"]): return "教育培训"
        if any(k in s for k in ["交通","站点","公交","停车"]): return "交通设施"
        if any(k in s for k in ["公共","银行","ATM"]): return "公共设施"
        if any(k in s for k in ["娱乐","运动","健身","公园"]): return "休闲娱乐"
        if any(k in s for k in ["酒店","宾馆","住宿"]): return "住宿服务"
        if any(k in s for k in ["公司","工厂","企业"]): return "公司企业"
    return "其他"

gaode["facility_type"] = gaode.apply(
    lambda r: resolve_ftype(r["name"], r.get("category1"), r.get("category2")), axis=1)

VT = {
    "bus_stop":"交通设施","kindergarten":"教育培训","school":"教育培训",
    "gym":"休闲娱乐","subway":"交通设施","supermarket":"购物服务",
    "bar":"餐饮服务","park":"休闲娱乐","clinic":"医疗保健",
    "hospital":"医疗保健","restaurant":"餐饮服务","bank":"公共设施",
    "pharmacy":"医疗保健","cinema":"休闲娱乐","hotel":"住宿服务",
    "cafe":"餐饮服务","convenience":"购物服务","parking":"交通设施","toilet":"公共设施",
}
v5["facility_type_v5"] = v5["facility_type"].apply(
    lambda x: VT.get(str(x).strip().lower(), "其他") if not pd.isna(x) else "其他")

# ── KDTree match ──
gaode_v = gaode.dropna(subset=["gcj_lon","gcj_lat"]).copy()
gaode_v["_lon"] = gaode_v["gcj_lon"].round(6)
gaode_v["_lat"] = gaode_v["gcj_lat"].round(6)
gt_pts = gaode_v[["_lon","_lat"]].values
tree = cKDTree(gt_pts)

v5_v = v5.dropna(subset=["gcj_lon","lat"]).copy()
v5_v["_lon"] = v5_v["gcj_lon"].round(6)
v5_v["_lat"] = v5_v["lat"].round(6)
v5_pts = v5_v[["_lon","_lat"]].values
distances, indices = tree.query(v5_pts)

THRESH = 0.001
mask = distances <= THRESH
m_gt_pos = indices[mask]
m_v5_pos = np.where(mask)[0]

updated_night = 0
for i in range(len(m_gt_pos)):
    gi = m_gt_pos[i]
    vi = m_v5_pos[i]
    g_row = gaode_v.index[gi]
    v_row = v5_v.iloc[vi]
    gaode.at[g_row, "v5_matched"] = True
    ns = v_row.get("night_service")
    if pd.notna(ns):
        gaode.at[g_row, "night_service"] = ns
        if str(ns).lower() == "true":
            updated_night += 1

print(f"\nV5 匹配: {len(m_gt_pos):,} 条 | V5 夜间: {updated_night} 条")

# ── Fine-grained inference ──
# Keyword sets
NIGHT_KW = {
    "24小时","24h","全天","通宵","24小时营业",
    "711","seven-eleven","7-11","全家","罗森","便利蜂",
    "美宜佳","天福","合家欢","快客",
    "麦当劳","麦道","KFC","肯德基","汉堡王","必胜客","吉野家","真功夫",
}
NO_NIGHT_KW = {
    "学校","幼儿园","中学","大学","学院",
    "政府","街道办","居委会","派出所",
    "银行","写字楼","政务","办事大厅",
}

def parse_v5(ns):
    if pd.isna(ns): return None
    s = str(ns).lower()
    if s == "true": return True
    if s == "false": return False
    return None

def infer_night(row):
    """精细化推断 v2"""
    ns_val = row.get("night_service")
    name   = str(row.get("name", ""))
    ft     = str(row.get("facility_type", "其他"))
    nl     = name.lower()

    # Priority 1: V5 direct label
    direct = parse_v5(ns_val)
    if direct is True:  return True
    if direct is False: return False

    # Priority 2: name keywords
    for kw in NIGHT_KW:
        if kw.lower() in nl: return True
    for kw in NO_NIGHT_KW:
        if kw in name: return False

    # Priority 3: type rules
    if ft == "医疗保健":
        if any(k in name for k in ["药店","门诊","卫生站","急诊"]): return True
        return False
    if ft == "购物服务":
        if any(k in name for k in ["便利店"]): return True
        if any(k in name for k in ["711","全家","罗森","便利蜂","美宜佳","天福"]): return True
        return False
    if ft == "交通设施":
        if any(k in name for k in ["地铁","地铁站","公交","站台","站点","驿站"]): return True
        return False
    if ft == "公共设施":
        if "ATM" in name: return True
        return False
    if ft == "餐饮服务":
        if any(k in name for k in ["麦当劳","麦道","KFC","肯德基","汉堡王","必胜客","吉野家","真功夫"]): return True
        return False
    if ft == "休闲娱乐":
        if any(k in name for k in ["影院","电影","KTV","ktv","棋牌","足浴","SPA","美容"]): return True
        return False
    if ft == "住宿服务":
        return True
    if ft in {"教育培训","政府机构","公司企业","商务写字楼"}:
        return False
    if ft == "生活服务":
        if any(k in name for k in ["快递","菜鸟","丰巢"]): return True
        return False
    return False

print("\n推断夜间服务...")
t0 = time.time()
gaode["night_service_final"] = gaode.apply(infer_night, axis=1)
print(f"推断完成: {time.time()-t0:.1f}s")

# ── Statistics ──
total     = len(gaode)
night_all = int(gaode["night_service_final"].sum())
night_v5  = sum(1 for _, r in gaode.iterrows() if parse_v5(r.get("night_service")) is True)
night_v5d = int(gaode[(gaode["v5_matched"]==True) & gaode["night_service"].apply(parse_v5).apply(lambda x: x is True)].shape[0])

print(f"\n{'='*60}")
print(f"夜间服务标注结果")
print(f"{'='*60}")
print(f"  总 POI:              {total:,}")
print(f"  V5 直接夜间:         {night_v5:,} ({100*night_v5/total:.1f}%)")
print(f"  推断夜间总计:         {night_all:,} ({100*night_all/total:.1f}%)")
print(f"  V5 贡献:             {night_v5d:,}")
print(f"  规则推断贡献:          {night_all-night_v5d:,}")

print(f"\n{'设施类型':<12} {'总数':>7} {'夜间':>8} {'占比':>7} {'V5标':>6}")
print("-" * 50)
for ft, grp in gaode.groupby("facility_type"):
    cnt = len(grp)
    ns  = int((grp["night_service_final"]==True).sum())
    v5n = sum(1 for _, r in grp.iterrows() if parse_v5(r.get("night_service")) is True)
    print(f"{ft:<12} {cnt:>7,} {ns:>8,} {100*ns/cnt:>6.1f}% {v5n:>6,}")

print(f"\n夜间服务 POI 分布:")
print(gaode[gaode["night_service_final"]==True]["facility_type"].value_counts().to_string())

# Compare with old version
try:
    old = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_integrated.csv",
                      usecols=["name","facility_type","night_service_final"], low_memory=False)
    old.columns = ["name","ftype","old_nsf"]
    mrg = gaode.merge(old, left_on=["name","facility_type"], right_on=["name","ftype"], how="left")
    changed = mrg[mrg["old_nsf"] != mrg["night_service_final"]]
    print(f"\n与旧版相比变化: {len(changed):,} 条")
    if len(changed) > 0:
        print("变化最大的设施类型:")
        print(changed.groupby("facility_type").size().sort_values(ascending=False).head(8).to_string())
except Exception as e:
    print(f"\n(旧版对比: {e})")

# ── Save ──
out_csv = OUT + r"\nanshan_poi_integrated_v2.csv"
out_json = OUT + r"\nanshan_poi_integrated_v2.json"
gaode.to_csv(out_csv, index=False, encoding="utf-8")
gaode.to_json(out_json, orient="records", force_ascii=False, indent=2)
print(f"\n✓ 已保存: {out_csv}")
print(f"✓ 已保存: {out_json}")
