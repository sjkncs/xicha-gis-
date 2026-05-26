# -*- coding: utf-8 -*-
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
poi = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_integrated.csv", low_memory=False)

print("=" * 70)
print("night_service_final 的生成逻辑反推")
print("=" * 70)

# 分析 night_service_final 与各设施类型的关系
print("\n【night_service_final=True 的设施类型分布】")
true_df = poi[poi['night_service_final'] == True]
print(true_df['facility_type'].value_counts().to_string())

print("\n【night_service_final=True 的详细分析】")
for ft, group in poi.groupby('facility_type'):
    t = (group['night_service_final'] == True).sum()
    f = (group['night_service_final'] == False).sum()
    if t > 0:
        pct = 100 * t / (t + f)
        # v5 matched among true
        v5_t = ((group['night_service_final'] == True) & (group['v5_matched'] == True)).sum()
        print(f"  {ft:20s}: True={t:,} ({pct:.1f}%) | v5_matched among True: {v5_t}")

print("\n【v5_matched=True 且 night_service=True 的记录】")
v5_true_ns = poi[(poi['v5_matched'] == True) & (poi['night_service'] == True)]
print(f"v5_matched + night_service=True: {len(v5_true_ns):,}")
if len(v5_true_ns) > 0:
    print(v5_true_ns[['name', 'facility_type', 'night_service', 'night_service_final']].head(10).to_string())

print("\n【v5_matched=True 且 night_service=False 的记录】")
v5_false_ns = poi[(poi['v5_matched'] == True) & (poi['night_service'] == False)]
print(f"v5_matched + night_service=False: {len(v5_false_ns):,}")
if len(v5_false_ns) > 0:
    print(v5_false_ns[['name', 'facility_type', 'night_service', 'night_service_final']].head(10).to_string())

print("\n【v5_matched=True 但 night_service=NaN 的记录】")
v5_nan_ns = poi[(poi['v5_matched'] == True) & (poi['night_service'].isna())]
print(f"v5_matched + night_service=NaN: {len(v5_nan_ns):,}")
if len(v5_nan_ns) > 0:
    print(v5_nan_ns[['name', 'facility_type', 'night_service', 'night_service_final']].head(10).to_string())
    print(f"\n这些 NaN 记录被推断为: True={((v5_nan_ns['night_service_final']==True).sum())}, False={((v5_nan_ns['night_service_final']==False).sum())}")
