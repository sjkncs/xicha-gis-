# -*- coding: utf-8 -*-
"""读取shapefile，找南山区边界"""
import shapefile, os, sys

sys.stdout.reconfigure(encoding='utf-8')

# ===== 1. 读取区级边界 (找南山区) =====
district_shp = r"E:\xicha gis 智能定位\GData2\区级边界New.shp"
sf_d = shapefile.Reader(district_shp, encoding='utf-8')

print("=== 区级边界 ===")
for i, rec in enumerate(sf_d.records()):
    d = dict(zip([f[0] for f in sf_d.fields[1:]], rec))
    print(f"  [{i}] sname={d['sname']!r}, area={d['area']:.2f}")

# 找南山区
nanshan_idx = None
for i, rec in enumerate(sf_d.records()):
    d = dict(zip([f[0] for f in sf_d.fields[1:]], rec))
    sname = d['sname']
    if '南山' in sname or 'Nanshan' in sname:
        nanshan_idx = i
        print(f"\n>>> 找到南山区: 索引={i}")

if nanshan_idx is None:
    print("\n未在sname中找到南山区，尝试用面积和bbox粗筛...")
    # Shenzhen districts: 南山区、福田区、罗湖区、宝安区、龙岗区、盐田区、龙华区、坪山区、光明区、大鹏新区
    shenzhen_districts = ['南山', '福田', '罗湖', '宝安', '龙岗', '盐田', '龙华', '坪山', '光明', '大鹏']
    for i, rec in enumerate(sf_d.records()):
        d = dict(zip([f[0] for f in sf_d.fields[1:]], rec))
        sname = d['sname']
        for kw in shenzhen_districts:
            if kw in sname:
                print(f"  [{i}] {sname!r} area={d['area']:.2f}")

# ===== 2. 读取POI点数据 =====
print("\n=== POI数据 ===")
poi_shp = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\poi.shp"
sf_p = shapefile.Reader(poi_shp, encoding='utf-8')

poi_fields = [f[0] for f in sf_p.fields[1:]]
print(f"POI记录数: {sf_p.numRecords}")
print(f"POI字段: {poi_fields[:10]}...")

# 统计有opening_hours的记录
has_hours = 0
for rec in sf_p.records():
    d = dict(zip(poi_fields, rec))
    if d.get('opening_ho', '').strip():
        has_hours += 1
print(f"有营业时间(opening_ho)的POI: {has_hours}")

# 看几条opening_hours样本
print("\n营业时间样本:")
count = 0
for rec in sf_p.records():
    d = dict(zip(poi_fields, rec))
    hours = d.get('opening_ho', '').strip()
    if hours:
        print(f"  name={d.get('name','')!r}, hours={hours!r}")
        count += 1
        if count >= 5:
            break

print("\n=== 南山区边界坐标范围 ===")
shapes = list(sf_d.iterShapes())
for i, shape in enumerate(shapes):
    if i == nanshan_idx:
        print(f"南山区: X({shape.bbox[0]:.2f}~{shape.bbox[2]:.2f}), Y({shape.bbox[1]:.2f}~{shape.bbox[3]:.2f})")
        break
else:
    # 打印所有边界
    for i, shape in enumerate(shapes):
        d = dict(zip([f[0] for f in sf_d.fields[1:]], sf_d.record(i)))
        print(f"[{i}] {d['sname']}: X({shape.bbox[0]:.0f}~{shape.bbox[2]:.0f}), Y({shape.bbox[1]:.0f}~{shape.bbox[3]:.0f})")

# PRJ 坐标系
prj_path = r"E:\xicha gis 智能定位\GData2\区级边界New.prj"
if os.path.exists(prj_path):
    with open(prj_path, 'r', encoding='utf-8', errors='ignore') as f:
        prj = f.read()
    print(f"\n边界坐标系: {prj[:100]}")

poi_prj_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\poi.prj"
if os.path.exists(poi_prj_path):
    with open(poi_prj_path, 'r', encoding='utf-8', errors='ignore') as f:
        prj2 = f.read()
    print(f"POI坐标系: {prj2[:100]}")
