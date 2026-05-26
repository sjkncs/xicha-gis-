# -*- coding: utf-8 -*-
"""快速分析 shapefile 结构"""
import shapefile, os

shp_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\广东省和地级市\广东省\广东省POI_2022.shp"
print(f"文件大小: {os.path.getsize(shp_path)/1024/1024:.1f} MB")

sf = shapefile.Reader(shp_path)
print(f"字段数: {len(sf.fields)}, 记录数: {sf.numRecords}")

# Print all field names
print("\n所有字段:")
for f in sf.fields:
    print(f"  {f}")

# Get bounding box
print(f"\n空间范围 (bbox):")
print(f"  Xmin={sf.bbox[0]:.4f}, Ymin={sf.bbox[1]:.4f}")
print(f"  Xmax={sf.bbox[2]:.4f}, Ymax={sf.bbox[3]:.4f}")

# Read first 5 records
print("\n前5条记录:")
for i, rec in enumerate(sf.records()[:5]):
    print(f"  [{i}] {rec}")
