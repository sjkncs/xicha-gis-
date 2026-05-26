# -*- coding: utf-8 -*-
"""对比各数据源，找出缺失和混入的南山区POI"""
import pandas as pd, sys, os

sys.stdout.reconfigure(encoding='utf-8')

base = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data"
gaode_f = os.path.join(base, "nanshan_poi_gaode.csv")

# 读取高德南山区完整数据（ground truth）
gaode = pd.read_csv(gaode_f, low_memory=False)
gaode_names = set(gaode['name'].dropna().astype(str).str.strip())
print(f"高德南山区 ground truth: {len(gaode)} 条, {len(gaode_names)} 个不同名称")

# 各类别
print("\n=== 高德南山区 POI 类型 ===")
print(gaode.groupby(['category1', 'category2']).size().sort_values(ascending=False).head(30).to_string())

# 对比各数据源
files_to_check = [
    ("nanshan_poi.csv", "高德API下载版"),
    ("nanshan_final_quick.csv", "快速版"),
    ("nanshan_quick_test.csv", "测试版"),
    ("nanshan_verify.csv", "验证版"),
    ("nanshan_osm_supplement.csv", "OSM补充"),
    ("nanshan_poi_all.csv", "OSM原始筛选"),
]

print("\n" + "="*70)
print("各数据源对比")
print("="*70)

all_found = set()  # 所有来源中出现过的不重复名称集合

for fname, label in files_to_check:
    fpath = os.path.join(base, fname)
    if not os.path.exists(fpath):
        print(f"\n{fname}: 文件不存在")
        continue
    
    df = pd.read_csv(fpath, low_memory=False)
    names = set(df['name'].dropna().astype(str).str.strip()) if 'name' in df.columns else set()
    
    # 高德中有但此文件没有的
    missing = gaode_names - names
    # 此文件有但高德中没有的
    extra = names - gaode_names
    # 共同的
    common = gaode_names & names
    
    print(f"\n【{label}】{fname}:")
    print(f"  总记录: {len(df)}, 不重名: {len(names)}")
    print(f"  与高德重叠: {len(common)},  高德缺失: {len(missing)},  混入(高德无): {len(extra)}")
    
    all_found |= names
    
    if extra:
        print(f"  [混入样本] {list(extra)[:5]}")
    if missing and len(missing) < 20:
        print(f"  [高德缺失] {list(missing)[:20]}")

# 统计整体缺失情况
print("\n" + "="*70)
print("汇总：所有数据源合并后仍缺失的 POI（高德有但都找不到）")
print("="*70)
total_missing = gaode_names - all_found
print(f"缺失: {len(total_missing)} / {len(gaode_names)} ({100*len(total_missing)/len(gaode_names):.1f}%)")
if len(total_missing) < 50:
    print(list(total_missing)[:50])
else:
    # 按类型统计缺失
    gaode_missing = gaode[gaode['name'].isin(total_missing)]
    print("\n缺失按类型:")
    print(gaode_missing.groupby(['category1', 'category2']).size().sort_values(ascending=False).head(20).to_string())

# 按类型统计覆盖率
print("\n=== 各 POI 类型覆盖率 ===")
for cat1, cat2, cnt in gaode.groupby(['category1', 'category2']).size().reset_index(name='total').itertuples(index=False):
    total = cnt
    found = sum(1 for n in gaode_names if n in all_found)  # approximate
    cat_names = set(gaode[(gaode['category1']==cat1) & (gaode['category2']==cat2)]['name'].dropna())
    cat_found = cat_names & all_found
    coverage = len(cat_found) / total * 100 if total > 0 else 0
    if coverage < 100:
        print(f"  {cat1}/{cat2}: {len(cat_found)}/{total} ({coverage:.0f}%)")
