# -*- coding: utf-8 -*-
import pandas as pd, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BDIR = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\building_data"
src = [f for f in os.listdir(BDIR) if '楼栋' in f or '房屋' in f][0]
path = os.path.join(BDIR, src)
print(f"File: {src}")

for enc in ['utf-8', 'utf-8-sig', 'gbk', 'gb18030', 'latin1']:
    try:
        df = pd.read_csv(path, encoding=enc, nrows=2)
        cols = list(df.columns)
        vals = list(df.iloc[0].values)
        print(f"\n{enc}: OK | cols={len(cols)}")
        print(f"  Cols: {cols}")
        print(f"  Row0: {vals}")
        # Check if any col has numeric values in lon/lat range
        for c in df.columns:
            v = df[c].dropna()
            if len(v) > 0 and pd.api.types.is_numeric_dtype(v):
                mn, mx = v.min(), v.max()
                if 22.4 <= mn and mx <= 22.7:
                    print(f"  -> '{c}' looks like LAT: {mn:.4f} - {mx:.4f}")
                if 113.8 <= mn and mx <= 114.0:
                    print(f"  -> '{c}' looks like LON: {mn:.4f} - {mx:.4f}")
    except Exception as e:
        print(f"\n{enc}: FAIL -> {e}")
