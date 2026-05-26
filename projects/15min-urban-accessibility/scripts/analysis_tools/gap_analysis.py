# -*- coding: utf-8 -*-
"""
评估两个核心缺口:
1. 夜间服务数据覆盖率（V5 API标注 vs 推断）
2. 社区POI数据（villages.db 中的设施密度）
"""
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# ── 1. POI 夜间服务覆盖率 ──
print("=" * 70)
print("【缺口1】夜间服务数据质量评估")
print("=" * 70)

poi = pd.read_csv(f"{BASE}\\osm_data\\nanshan_poi_integrated.csv", low_memory=False)
print(f"\n总 POI 记录数: {len(poi):,}")
print(f"\n列名: {list(poi.columns)}")

# night_service_final 分布
if 'night_service_final' in poi.columns:
    ns = poi['night_service_final'].value_counts(dropna=False)
    print(f"\nnight_service_final 分布:")
    print(ns)
    
    # 有标注 vs 无标注
    labeled = poi['night_service_final'].notna().sum()
    unlabeled = poi['night_service_final'].isna().sum()
    print(f"\n  有夜间标注: {labeled:,} ({100*labeled/len(poi):.1f}%)")
    print(f"  无夜间标注: {unlabeled:,} ({100*unlabeled/len(poi):.1f}%)")
else:
    print("night_service_final 列不存在")

# 设施类型分布
if 'facility_type' in poi.columns:
    print(f"\n设施类型分布 (Top 20):")
    ft = poi['facility_type'].value_counts().head(20)
    for name, cnt in ft.items():
        print(f"  {name:20s}: {cnt:,}")

# ── 2. 社区数据完整性 ──
print("\n" + "=" * 70)
print("【缺口2】社区数据完整性评估")
print("=" * 70)

import sqlite3
conn = sqlite3.connect(f"{BASE}\\village_data\\villages.db")
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"\n数据库表: {tables}")

if 'sz_village' in tables:
    v = pd.read_sql("SELECT * FROM sz_village LIMIT 3", conn)
    print(f"\nsz_village 列: {list(v.columns)}")
    total = pd.read_sql("SELECT COUNT(*) FROM sz_village", conn).iloc[0,0]
    print(f"总记录: {total:,}")
    
    with_coords = pd.read_sql(
        "SELECT COUNT(*) FROM sz_village WHERE lng IS NOT NULL AND lat IS NOT NULL", conn
    ).iloc[0,0]
    print(f"有坐标: {with_coords:,}")
    
    # 小区类型分布
    if 'community_type' in v.columns:
        types = pd.read_sql("SELECT community_type, COUNT(*) FROM sz_village GROUP BY community_type", conn)
        print(f"\n小区类型分布:")
        print(types.to_string(index=False))
