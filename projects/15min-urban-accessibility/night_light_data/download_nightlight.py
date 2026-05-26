# -*- coding: utf-8 -*-
"""
夜间灯光数据下载脚本
数据源: World Bank "Light Every Night" AWS S3 (public bucket)
      VIIRS-DNB monthly aggregates covering 2012-present
目标: 下载覆盖深圳南山区的夜间灯光数据，辅助说明可达性幻觉-AOI
"""
import os, sys, io, json, math, re, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUTDIR = os.path.join(BASE, "night_light_data")
os.makedirs(OUTDIR, exist_ok=True)

# Nanshan District bounds (WGS84): 113.85-113.96E, 22.48-22.60N
# At 15arc-sec resolution (~500m), we need coarse-level data
# Using AWS S3 public bucket: s3://globalnightlight/

# ---- 检查 requests 能否访问 S3 ----
import requests

# Test: list a monthly folder via HTTP (S3 public)
def s3_list_objects(prefix):
    """List S3 objects via HTTP (public bucket, no auth needed)"""
    url = f"https://globalnightlight.s3.amazonaws.com/?list-type=2&prefix={prefix}"
    r = requests.get(url, timeout=30)
    if r.status_code == 200:
        # Parse XML
        import re
        keys = re.findall(r'<Key>(.*?)</Key>', r.text)
        return keys
    else:
        return []

# ---- 获取2012年至今的年度月度夜间灯光 ----
# 策略: 下载月度合成数据，提取南山区平均亮度
# 数据目录: https://globalnightlight.s3.amazonaws.com/201505/

# 先测试2023年月度数据（较新）
test_prefixes = ["202301/", "202312/", "202401/", "202412/"]
print("[1] Testing S3 bucket access:")
for p in test_prefixes:
    url = f"https://globalnightlight.s3.amazonaws.com/{p}"
    r = requests.head(url, timeout=10)
    print(f"    {p}: {r.status_code}")

# ---- 如果S3可用，列出所有月份 ----
print("\n[2] Listing available months (2023):")
keys = s3_list_objects("202312/")
print(f"    Total files: {len(keys)}")
if keys:
    print(f"    Sample files: {keys[:5]}")
