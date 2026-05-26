# -*- coding: utf-8 -*-
"""
P0: 夜间服务标注逻辑诊断与修复
分析当前 night_service_final 的生成逻辑，找出问题所在
"""
import pandas as pd, numpy as np, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
poi = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_integrated.csv", low_memory=False)

print("=" * 70)
print("P0: 夜间标注逻辑诊断")
print("=" * 70)
print(f"\n总记录: {len(poi):,}")

# 关键列分析
print("\n【各设施类型的 night_service 分布】")
print("-" * 70)
if 'night_service' in poi.columns and 'facility_type' in poi.columns:
    for ft, group in poi.groupby('facility_type'):
        total = len(group)
        ns_vals = group['night_service'].value_counts(dropna=False)
        print(f"\n{ft} (n={total:,}):")
        for val, cnt in ns_vals.items():
            tag = "✓" if val is True or val == True else "✗" if val is False else "?"
            print(f"  night_service={val!s:5s} {tag}: {cnt:,} ({100*cnt/total:.1f}%)")

print("\n【v5_matched 分布】")
if 'v5_matched' in poi.columns:
    print(poi['v5_matched'].value_counts(dropna=False))

print("\n【night_service_final vs night_service 对比】")
if 'night_service_final' in poi.columns:
    diff = poi[poi['night_service_final'] != poi['night_service']]
    print(f"不一致的记录: {len(diff):,} 条")
    if len(diff) > 0:
        # 按不一致的原因分类
        print("\n不一致的原因分析:")
        # night_service=True 但 final=False
        f_t = poi[(poi['night_service'] == True) & (poi['night_service_final'] == False)]
        t_f = poi[(poi['night_service'] == False) & (poi['night_service_final'] == True)]
        print(f"  True→False (被覆盖): {len(f_t):,}")
        print(f"  False→True (被覆盖): {len(t_f):,}")
        if len(f_t) > 0:
            print(f"\n  被错误降级为False的设施类型:")
            print(f_t['facility_type'].value_counts().head(10).to_string())
        if len(t_f) > 0:
            print(f"\n  被错误升级为True的设施类型:")
            print(t_f['facility_type'].value_counts().head(10).to_string())
