# -*- coding: utf-8 -*-
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')

df = pd.read_csv('building_data/南山区-房屋楼栋基础数据_2920004003598.csv', dtype=str, keep_default_na=False)
print('Total records:', len(df))
print('Columns:', list(df.columns))

lng = pd.to_numeric(df.iloc[:, 1], errors='coerce')
lat = pd.to_numeric(df.iloc[:, 2], errors='coerce')
print('lng range: %.4f ~ %.4f' % (lng.min(), lng.max()))
print('lat range: %.4f ~ %.4f' % (lat.min(), lat.max()))

type_map = {0:'Other',1:'Residential',2:'Mixed Res-Comm',3:'Commercial',
            4:'Office',5:'Public',6:'Industrial',7:'Special',8:'Education',9:'Medical'}
print()
print('Usage Type Distribution (code -> meaning -> count):')
for v, cnt in df.iloc[:, 6].value_counts().sort_index().items():
    pct = 100.0 * int(cnt) / len(df)
    meaning = type_map.get(int(v), '?')
    print('  type=%s=%s: %s (%.1f%%)' % (v, meaning, cnt, pct))

floors = pd.to_numeric(df.iloc[:, 8], errors='coerce')
print()
print('Floor stats: mean=%.1f, median=%.0f, max=%.0f' % (floors.mean(), floors.median(), floors.max()))

print()
print('Sample (top 5):')
print(df[['名称', '常用地址', '使用用途', '总层数']].head(5).to_string())
