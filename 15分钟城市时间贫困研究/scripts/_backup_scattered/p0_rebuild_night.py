# -*- coding: utf-8 -*-
"""
P0: 重建 night_service_final — 精细化推断逻辑
核心问题：交通设施/休闲娱乐 全量被推断为夜间服务（不符实际）
新策略：
  1. V5 直接标注 → 保留
  2. 名中含"24h/24小时" → True
  3. 类型→概率推断（而非二元开关）
  4. 关键设施（医疗/便利店）→ 提升置信度
"""
import pandas as pd, numpy as np, sys, io, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT  = BASE + r"\osm_data"

print("=" * 70)
print("P0: 重建夜间服务标注（精细化推断）")
print("=" * 70)

# ── 加载原始 Ground Truth 数据 ──
gaode = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_gaode.csv", low_memory=False)
v5    = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_v5.csv",   low_memory=False)
print(f"Ground Truth: {len(gaode):,} 条")
print(f"V5 API:       {len(v5):,} 条")

# ── 列名标准化 ──
gaode.rename(columns={"lon": "gcj_lon", "lat": "gcj_lat"}, inplace=True)
gaode["night_service"] = None
gaode["v5_matched"] = False
v5.rename(columns={"lng": "gcj_lon"}, inplace=True)

# ── 设施类型分类（复用原有逻辑） ──
TYPE_PATTERNS = [
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
    for ftype, kws in TYPE_PATTERNS:
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

# ── V5 英文类型映射 ──
V5_TYPE_MAP = {
    "bus_stop":"交通设施","kindergarten":"教育培训","school":"教育培训",
    "gym":"休闲娱乐","subway":"交通设施","supermarket":"购物服务",
    "bar":"餐饮服务","park":"休闲娱乐","clinic":"医疗保健",
    "hospital":"医疗保健","restaurant":"餐饮服务","bank":"公共设施",
    "pharmacy":"医疗保健","cinema":"休闲娱乐","hotel":"住宿服务",
    "cafe":"餐饮服务","convenience":"购物服务","parking":"交通设施",
    "toilet":"公共设施",
}
v5["facility_type_v5"] = v5["facility_type"].apply(
    lambda x: V5_TYPE_MAP.get(str(x).strip().lower(), "其他") if not pd.isna(x) else "其他")

# ── 空间匹配 KDTree ──
from scipy.spatial import cKDTree
gaode_valid = gaode.dropna(subset=["gcj_lon","gcj_lat"]).copy()
gaode_valid["_lon"] = gaode_valid["gcj_lon"].round(6)
gaode_valid["_lat"] = gaode_valid["gcj_lat"].round(6)
gaode_pts = gaode_valid[["_lon","_lat"]].values
tree = cKDTree(gaode_pts)

v5_valid = v5.dropna(subset=["gcj_lon","lat"]).copy()
v5_valid["_lon"] = v5_valid["gcj_lon"].round(6)
v5_valid["_lat"] = v5_valid["lat"].round(6)
v5_pts = v5_valid[["_lon","_lat"]].values
distances, indices = tree.query(v5_pts)

THRESHOLD = 0.001
mask = distances <= THRESHOLD
matched_gt_pos = indices[mask]
matched_v5_pos = np.where(mask)[0]

# 写入 V5 标注
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

print(f"\nV5 匹配: {len(matched_gt_pos):,} 条")
print(f"V5 夜间服务标注: {updated_night} 条")

# ── 精细化推断函数（替代原有逻辑） ──
# 策略：类型+名称关键词双判断，避免全量二元开关
KNOWN_NIGHT_NAMES = {
    # 明确的24h设施名称关键词
    "24小时", "24h", "全天", "通宵", "24小时营业",
    # 知名连锁便利店（几乎全部24h）
    "711", "seven-eleven", "7-11", "全家", "罗森", "便利蜂",
    "美宜佳", "天福", "合家欢", "快客",
    # 知名连锁快餐（部分24h）
    "麦当劳", "麦道", "KFC", "肯德基", "汉堡王",
    "必胜客", "真功夫", "吉野家", "味千",
}

KNOWN_NO_NIGHT_NAMES = {
    # 明确夜间关闭
    "学校", "幼儿园", "中学", "大学", "学院",
    "政府", "街道办", "居委会", "派出所",
    "银行", "写字楼",
}

def is_night_true(ns):
    if pd.isna(ns): return None
    s = str(ns).lower()
    if s == "true": return True
    if s == "false": return False
    return None

def infer_night_service_v2(row):
    """
    精细化夜间服务推断 v2
    优先级：V5直接 > 名称关键词 > 类型概率推断
    """
    name = str(row.get("name", ""))
    ft   = str(row.get("facility_type", "其他"))
    
    # ── Step 1: V5 直接标注（最高优先级） ──
    direct = is_night_true(row.get("night_service")))
    if direct is True:   return True
    if direct is False:  return False
    
    # ── Step 2: 名称关键词判断 ──
    name_lower = name.lower()
    for kw in KNOWN_NIGHT_NAMES:
        if kw.lower() in name_lower:
            return True
    for kw in KNOWN_NO_NIGHT_NAMES:
        if kw in name:
            return False
    
    # ── Step 3: 类型概率推断（区分对待） ──
    # ★ 关键设施：医疗/便利店 → 高概率
    if ft == "医疗保健":
        if any(k in name for k in ["药店","门诊","卫生站","急诊"]):
            return True
        return False  # 医院/诊所夜间一般关闭（急诊例外）
    
    if ft == "购物服务":
        if any(k in name for k in ["便利店","24","24h","全天"]):
            return True
        # 知名24h便利店连锁
        if any(k in name for k in ["711","全家","罗森","便利蜂","美宜佳","天福"]):
            return True
        return False  # 商场/超市夜间关闭（除24h）
    
    # ★ 交通设施：地铁/公交站 → 夜间有，但停车场/停车楼 → 无
    if ft == "交通设施":
        if any(k in name for k in ["地铁","地铁站","公交","站台","站点","驿站"]):
            return True
        if any(k in name for k in ["停车场","停车","停车楼","P+R"]):
            return False
        return False  # 不明确 → 保守
    
    # ★ 公共设施：ATM → True, 公共厕所 → 部分24h, 银行 → False
    if ft == "公共设施":
        if "ATM" in name or "atm" in name_lower:
            return True
        if "银行" in name or "公共厕所" in name:
            return False
        return False
    
    # ★ 餐饮服务：知名快餐连锁 → 部分24h
    if ft == "餐饮服务":
        if any(k in name for k in ["麦当劳","麦道","KFC","肯德基","汉堡王","必胜客","吉野家","真功夫"]):
            return True  # 知名快餐有一定概率24h
        return False  # 餐厅/食堂夜间关闭
    
    # ★ 休闲娱乐：影院/KTV → 夜间营业（已有V5匹配覆盖）
    if ft == "休闲娱乐":
        if any(k in name for k in ["影院","电影","KTV","ktv","棋牌","足浴","SPA","美容"]):
            return True
        return False  # 健身/公园/游乐 → 夜间关闭
    
    # ★ 住宿服务：酒店 → 24h
    if ft == "住宿服务":
        return True  # 酒店前台24h
    
    # ★ 教育培训/政府机构/公司企业 → 夜间关闭
    if ft in {"教育培训", "政府机构", "公司企业", "商务写字楼"}:
        return False
    
    # ★ 生活服务：快递 → 部分24h
    if ft == "生活服务":
        if any(k in name for k in ["快递","菜鸟","丰巢","24"]):
            return True
        return False
    
    # 其他：保守默认夜间关闭
    return False

# ── 执行推断 ──
print("\n正在推断夜间服务...")
t0 = time.time()
gaode["night_service_final"] = gaode.apply(infer_night_service_v2, axis=1)
print(f"推断完成，耗时 {time.time()-t0:.1f}s")

# ── 结果统计 ──
print("\n" + "=" * 60)
print("【夜间服务标注统计】")
print("=" * 60)

total = len(gaode)
night_final = gaode["night_service_final"].sum()
night_v5    = (gaode["night_service"].apply(is_night_true) == True).sum()
night_v5_direct = int(gaode[(gaode["v5_matched"]==True) & (gaode["night_service"].apply(is_night_true) == True)].shape[0])

print(f"\n总 POI:           {total:,}")
print(f"V5 直接标注夜间:   {night_v5:,} ({100*night_v5/total:.1f}%)")
print(f"推断夜间总计:      {night_final:,} ({100*night_final/total:.1f}%)")
print(f"其中V5贡献:        {night_v5_direct:,}")
print(f"推断贡献:          {night_final - night_v5_direct:,}")

print(f"\n{'设施类型':<12} {'总数':>7} {'夜间':>8} {'占比':>7} {'V5直标':>7}")
print("-" * 55)
vc = gaode["facility_type"].value_counts()
for ft, cnt in vc.items():
    ns = (gaode[gaode["facility_type"]==ft]["night_service_final"] == True).sum()
    v5n = (gaode[gaode["facility_type"]==ft]["night_service"].apply(is_night_true) == True).sum()
    print(f"{ft:<12} {cnt:>7,} {ns:>8,} {100*ns/cnt:>6.1f}% {v5n:>7,}")

print(f"\n夜间服务 POI 分布:")
print(gaode[gaode["night_service_final"]==True]["facility_type"].value_counts().to_string())

# ── 对比旧版 vs 新版 ──
old_poi = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_integrated.csv", low_memory=False,
                        usecols=["name","facility_type","night_service_final"])
old_poi.columns = ["name","facility_type","old_nsf"]
merged = gaode.merge(old_poi, on=["name","facility_type"], how="left")
changed = merged[merged["old_nsf"] != merged["night_service_final"]]
print(f"\n与旧版相比，标注变化: {len(changed):,} 条")
if len(changed) > 0:
    print("\n变化最大的设施类型:")
    print(changed.groupby("facility_type").size().sort_values(ascending=False).head(8).to_string())

# ── 保存 ──
out_csv = OUT + r"\nanshan_poi_integrated_v2.csv"
out_json = OUT + r"\nanshan_poi_integrated_v2.json"
gaode.to_csv(out_csv, index=False, encoding="utf-8")
gaode.to_json(out_json, orient="records", force_ascii=False, indent=2)
print(f"\n✓ 已保存: {out_csv}")
print(f"✓ 已保存: {out_json}")
