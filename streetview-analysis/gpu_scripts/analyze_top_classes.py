#!/usr/bin/env python3
"""分析远端 seg_results.csv，找出模型实际预测最多的 top-20 类别 ID 分布"""
import csv
from pathlib import Path

# 先把结果下载到本地
import paramiko
HOST = 'connect.bjb1.seetacloud.com'; PORT = 12996
USER = 'root'; PASS = 'roBbKv+ed3Vm'

REMOTE_CSV = '/root/gis_project/outputs/segmentation/seg_results.csv'
LOCAL_CSV  = Path(__file__).parent / 'results' / 'seg_results_top20.csv'

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

sftp = c.open_sftp()
sftp.get(REMOTE_CSV, str(LOCAL_CSV))
sftp.close()
c.close()

print(f"Downloaded: {LOCAL_CSV}  ({LOCAL_CSV.stat().st_size} bytes)")

# 从 seg_results.csv 提取被统计过的 building/road/green/sky 的 pct 分布，
# 再根据 pct 推断实际类别分布偏差。
# 但更直接的方式是：在远端跑一段 Python 直接统计每张图的 argmax class id 频率。
# 这里先用本地 CSV 分析 pct 分布。
import json, csv as _csv
rows = list(_csv.DictReader(open(LOCAL_CSV, encoding='utf-8')))
print(f"Rows: {len(rows)}")
for k in ['pct_building','pct_road','pct_green','pct_sky',
          'pct_sidewalk','pct_vehicle','pct_person','pct_water']:
    vals = [float(r[k]) for r in rows if k in r]
    if vals:
        print(f"  {k:20s}: mean={sum(vals)/len(vals):.2f}%  "
              f"median={sorted(vals)[len(vals)//2]:.2f}%  "
              f"max={max(vals):.2f}%")
