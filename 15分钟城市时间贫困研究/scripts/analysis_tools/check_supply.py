# -*- coding: utf-8 -*-
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
v2 = pd.read_csv(BASE + r"\osm_data\nanshan_poi_integrated_v2.csv", low_memory=False)

print("nanshan_poi_integrated_v2.csv 列:")
print(v2.columns.tolist())
print()
print("supply 列:")
if 'supply' in v2.columns:
    print(v2['supply'].describe())
    print("Non-null: {}".format(v2['supply'].notna().sum()))
    print("Unique values: {}".format(v2['supply'].nunique()))
    print("Sample values:", v2['supply'].value_counts().head(10).to_dict())
else:
    print("NOT FOUND in v2.csv")
print()
print("night_service_final 列:")
if 'night_service_final' in v2.columns:
    print(v2['night_service_final'].value_counts())
else:
    print("NOT FOUND")
print()
print("facility_type vs supply cross-tab (sample):")
if 'supply' in v2.columns:
    for ft, grp in v2.groupby('facility_type'):
        if grp['supply'].notna().any() and grp['supply'].nunique() > 1:
            print("  {}: supply values = {}".format(
                ft, grp['supply'].value_counts().head(3).to_dict()))
