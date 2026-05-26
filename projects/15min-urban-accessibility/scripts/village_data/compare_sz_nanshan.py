# -*- coding: utf-8 -*-
"""
对比分析：深圳市POI数据.csv vs nanshan_poi_integrated.csv
找出深圳市数据中南山区记录，检查是否有多余或重叠
"""
import pandas as pd, numpy as np, sys
from scipy.spatial import cKDTree

sys.stdout.reconfigure(encoding='utf-8')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# ============================================================
# 1. 加载深圳市完整数据
# ============================================================
# 深圳市POI数据.csv 列：name, category1, category2, lon, lat, 省, 市, 区
sz = pd.read_csv(BASE + r"\广东省和地级市\广东省POI数据\深圳市POI数据.csv",
                  header=None,
                  names=["name", "category1", "category2", "lon", "lat",
                         "province", "city", "district"],
                  low_memory=False, dtype={"lon": str, "lat": str})
print(f"深圳市 POI 总数: {len(sz)}")
print(f"各区分布:\n{sz['district'].value_counts().to_string()}")
print()

# ============================================================
# 2. 筛选南山区记录
# ============================================================
nanshan_sz = sz[sz["district"].str.contains("南山", na=False)].copy()
print(f"深圳市数据中南山区记录: {len(nanshan_sz)} 条")

# ============================================================
# 3. 加载已整合数据
# ============================================================
integrated = pd.read_csv(BASE + r"\osm_data\nanshan_poi_integrated.csv", low_memory=False)
print(f"nanshan_poi_integrated.csv 记录: {len(integrated)} 条")
print(f"已整合数据列: {integrated.columns.tolist()}")

# ============================================================
# 4. 检查两数据集列结构差异
# ============================================================
print(f"\n深圳市数据列: {sz.columns.tolist()}")
print(f"已整合数据列: {integrated.columns.tolist()}")

# ============================================================
# 5. 空间重叠分析（KDTree）
# ============================================================
# 深圳市南山区数据
ns_sz_valid = nanshan_sz.dropna(subset=["lon", "lat"]).copy()
ns_sz_valid["_lon"] = pd.to_numeric(ns_sz_valid["lon"], errors="coerce").round(6)
ns_sz_valid["_lat"] = pd.to_numeric(ns_sz_valid["lat"], errors="coerce").round(6)

# 已整合数据
int_valid = integrated.dropna(subset=["gcj_lon", "gcj_lat"]).copy()
int_valid["_lon"] = int_valid["gcj_lon"].round(6)
int_valid["_lat"] = int_valid["gcj_lat"].round(6)

print(f"\n深圳市南山区有效坐标: {len(ns_sz_valid)}")
print(f"已整合有效坐标: {len(int_valid)}")

# 建立 KDTree（以已整合数据为基准）
int_pts = int_valid[["_lon", "_lat"]].values
tree = cKDTree(int_pts)

# 查询深圳市南山区记录在已整合数据中的匹配情况
sz_pts = ns_sz_valid[["_lon", "_lat"]].values
distances, indices = tree.query(sz_pts)

THRESHOLD = 0.0005  # ~55m
matched = distances <= THRESHOLD
print(f"\n空间匹配结果（阈值 {THRESHOLD} deg ≈ {THRESHOLD*111000:.0f}m）:")
print(f"  深圳市南山区记录: {len(ns_sz_valid)}")
print(f"  在已整合数据中有匹配: {matched.sum()} ({matched.sum()/len(ns_sz_valid)*100:.1f}%)")
print(f"  精确匹配(d=0): {(distances == 0).sum()}")
print(f"  近似匹配(<=55m): {matched.sum()}")

# ============================================================
# 6. 找出深圳市数据中多出的南山区 POI
# ============================================================
extra_sz = ns_sz_valid[~matched].copy()
print(f"\n深圳市数据中可能的额外南山区 POI（未匹配）: {len(extra_sz)} 条")

# 对多出的记录，在更大范围内再查一次
if len(extra_sz) > 0:
    extra_pts = extra_sz[["_lon", "_lat"]].values
    d2, i2 = tree.query(extra_pts)
    print(f"  扩大范围到 500m:")
    for thresh in [0.001, 0.005, 0.01]:
        n = (d2 <= thresh).sum()
        print(f"    d<={thresh:.3f} ({thresh*111000:.0f}m): {n} 条")

# ============================================================
# 7. 名称重叠检查
# ============================================================
print(f"\n名称重叠检查:")
# 深圳市南山区记录的唯一名称
sz_names = set(ns_sz_valid["name"].dropna().str.strip().str.lower())
# 已整合数据的名称
int_names = set(integrated["name"].dropna().str.strip().str.lower())
overlap = sz_names & int_names
only_sz = sz_names - int_names
print(f"  深圳市南山区唯一名称: {len(sz_names)}")
print(f"  已整合唯一名称: {len(int_names)}")
print(f"  名称重叠: {len(overlap)}")
print(f"  仅在深圳市数据中存在: {len(only_sz)}")

# ============================================================
# 8. 数据质量对比
# ============================================================
print(f"\n数据质量对比:")
print(f"  深圳市数据: {len(ns_sz_valid)} 条, 覆盖范围 lon[{ns_sz_valid['lon'].min():.4f}~{ns_sz_valid['lon'].max():.4f}]")
print(f"  已整合数据: {len(integrated)} 条, 覆盖范围 lon[{integrated['gcj_lon'].min():.4f}~{integrated['gcj_lon'].max():.4f}]")

# ============================================================
# 9. 建议：是否需要合并
# ============================================================
total_unique = len(int_names | sz_names)
print(f"\n{'='*50}")
print(f"【数据合并建议】")
print(f"{'='*50}")
print(f"  深圳市南山区数据: {len(ns_sz_valid)} 条")
print(f"  已整合数据: {len(integrated)} 条")
print(f"  合并后理论最大: {total_unique} 条")
print(f"  实际额外可补充: {len(only_sz)} 条名称")
print(f"  额外 POI 地理覆盖率: {len(extra_sz)} 条（空间上）")

if len(extra_sz) > 0 and len(only_sz) > 0:
    print(f"\n建议：可以将深圳市数据中的 {len(extra_sz)} 条南山区额外 POI 合并进来")
    print(f"      （其中 {len(only_sz)} 条名称在已整合数据中不存在）")
else:
    print(f"\n结论：深圳市南山区数据与已整合数据高度重叠，无需额外合并")
