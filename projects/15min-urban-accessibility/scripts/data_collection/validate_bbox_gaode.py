# -*- coding: utf-8 -*-
"""用高德API返回的 南山区 标注数据，精确确定BBOX边界并验证过滤准确性"""
import pandas as pd, sys, os
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

f = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\广东省和地级市\广东省POI数据\深圳市POI数据.csv"
df = pd.read_csv(f, low_memory=False)

print(f"总记录数: {len(df)}")
print(f"区域分布:\n{df['区域'].value_counts().to_string()}\n")

# ===== 1. 精确统计南山区 ======
ns = df[df['区域'] == '南山区'].copy()
print(f"=== 南山区 (区域字段标注) ===")
print(f"记录数: {len(ns)}")

# 坐标范围
ns_lon_min, ns_lon_max = ns['经度'].min(), ns['经度'].max()
ns_lat_min, ns_lat_max = ns['纬度'].min(), ns['纬度'].max()
print(f"Lon: {ns_lon_min:.5f} ~ {ns_lon_max:.5f}")
print(f"Lat: {ns_lat_min:.5f} ~ {ns_lat_max:.5f}")

# 去掉明显异常的边界点
ns_clean = ns[(ns['经度'] > 113.5) & (ns['经度'] < 114.5) &
              (ns['纬度'] > 22.0) & (ns['纬度'] < 23.0)].copy()
print(f"\n去除离群点后: {len(ns_clean)}")
ns_lon_min2, ns_lon_max2 = ns_clean['经度'].min(), ns_clean['经度'].max()
ns_lat_min2, ns_lat_max2 = ns_clean['纬度'].min(), ns_clean['纬度'].max()
print(f"Lon[clean]: {ns_lon_min2:.5f} ~ {ns_lon_max2:.5f}")
print(f"Lat[clean]: {ns_lat_min2:.5f} ~ {ns_lat_min2:.5f}")

# ===== 2. 分析各类型在南山区的情况 ======
print(f"\n=== 南山区 POI 类型分布 ===")
print(ns_clean['大类'].value_counts().to_string())
print()
print(ns_clean['中类'].value_counts().head(20).to_string())

# ===== 3. 验证 BBOX 过滤的准确性 ======
print(f"\n=== BBOX 过滤验证 ===")

# 用南山区精确范围作为BBOX
BBOX = {
    'lon_min': ns_lon_min2,
    'lon_max': ns_lon_max2,
    'lat_min': ns_lat_min2,
    'lat_max': ns_lat_max2,
}

def in_bbox(row):
    return (BBOX['lon_min'] <= row['经度'] <= BBOX['lon_max'] and
            BBOX['lat_min'] <= row['纬度'] <= BBOX['lat_max'])

# 用区域字段验证BBOX准确性
df_clean = df[(df['经度'] > 113.5) & (df['经度'] < 114.5) &
              (df['纬度'] > 22.0) & (df['纬度'] < 23.0)].copy()

df_clean['in_bbox'] = df_clean.apply(in_bbox, axis=1)
bbox_candidates = df_clean[df_clean['in_bbox']]

print(f"全深圳 BBOX 内 POI 总数: {len(bbox_candidates)}")
print(f"\nBBOX内各区分布:")
print(bbox_candidates['区域'].value_counts().to_string())

# 漏检率：南山区标注 POI 中，被BBOX漏掉的
ns_ids = set(ns_clean.index)
bbox_ns_ids = set(bbox_candidates.index) & ns_ids
missed = ns_ids - bbox_ns_ids
print(f"\n南山区 POI 漏检数: {len(missed)} / {len(ns_clean)} ({100*len(missed)/len(ns_clean):.1f}%)")

# 误检率：非南山区 POI 被BBOX误判
non_ns_in_bbox = len(bbox_candidates) - len(bbox_candidates[bbox_candidates['区域'] == '南山区'])
ns_total = len(bbox_candidates[bbox_candidates['区域'] == '南山区'])
print(f"BBOX内非南山误检数: {non_ns_in_bbox} / {len(bbox_candidates)} ({100*non_ns_in_bbox/len(bbox_candidates):.1f}%)")

# ===== 4. 细粒度：BBOX 扩边 + 区域双重过滤 ======
print(f"\n=== BBOX + 区域字段双重过滤 ===")
for district in ['南山区', '福田区', '宝安区', '罗湖区', '龙岗区', '龙华区', '盐田区', '坪山区', '光明区', '大鹏新区']:
    sub = df_clean[(df_clean['区域'] == district)]
    bbox_sub = sub[sub['in_bbox']]
    print(f"  {district}: 区内{bbox_sub['区域'].value_counts().sum()}条在BBOX内")

# ===== 5. 各 POI 类型在南山区的数量 ======
print(f"\n=== 各 POI 类型在南山区的数量 ===")
ns_counts = ns_clean.groupby(['大类', '中类']).size().reset_index(name='count')
ns_counts = ns_counts.sort_values('count', ascending=False)
print(ns_counts.head(30).to_string(index=False))

# ===== 6. 保存南山区完整数据 ======
ns_clean['lon'] = ns_clean['经度']
ns_clean['lat'] = ns_clean['纬度']
ns_clean = ns_clean.rename(columns={'名称': 'name', '大类': 'category1', '中类': 'category2'})
out = ns_clean[['lon', 'lat', 'name', 'category1', 'category2']].copy()
out_path = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究\osm_data\nanshan_poi_gaode.csv"
out.to_csv(out_path, index=False, encoding='utf-8-sig')
print(f"\n已保存南山区POI到: {out_path} (共{len(out)}条)")

# ===== 7. 输出推荐的BBOX ======
print(f"\n=== 推荐 BBOX 参数 ===")
print(f"  BBOX = {{")
print(f"    'lon_min': {ns_lon_min2:.6f},")
print(f"    'lon_max': {ns_lon_max2:.6f},")
print(f"    'lat_min': {ns_lat_min2:.6f},")
print(f"    'lat_max': {ns_lat_max2:.6f},")
print(f"  }}")
print(f"  # 原始多边形方法: 113.7859~114.0267, 22.2795~22.6525")
print(f"  # 高德南山区BBOX: {ns_lon_min2:.6f}~{ns_lon_max2:.6f}, {ns_lat_min2:.6f}~{ns_lat_min2:.6f}")
