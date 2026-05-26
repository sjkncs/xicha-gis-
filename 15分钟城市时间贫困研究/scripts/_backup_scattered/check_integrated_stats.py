# -*- coding: utf-8 -*-
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

df = pd.read_csv(r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\nanshan_poi_integrated.csv")
print(f"Total rows: {len(df)}")
print(f"\nfacility_type distribution:\n{df['facility_type'].value_counts()}")
print(f"\nnight_service_final distribution:\n{df['night_service_final'].value_counts(dropna=False)}")
print(f"\nColumn types:\n{df.dtypes}")
print(f"\nSample:\n{df[['name','facility_type','gcj_lon','gcj_lat','night_service_final']].head(10)}")
