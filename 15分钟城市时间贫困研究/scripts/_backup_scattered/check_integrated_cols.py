# -*- coding: utf-8 -*-
import pandas as pd, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

df = pd.read_csv(r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\nanshan_poi_integrated.csv", nrows=3)
print("Columns:", list(df.columns))
print("\nDtypes:")
print(df.dtypes)
print("\nSample night_service_final:")
print(df["night_service_final"].value_counts(dropna=False))
print("\nSample facility_type:")
print(df["facility_type"].value_counts(dropna=False))
print("\nSample rows:")
print(df[["name", "facility_type", "gcj_lon", "gcj_lat", "night_service_final", "supply"]].head())
