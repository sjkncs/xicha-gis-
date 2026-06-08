# -*- coding: utf-8 -*-
"""进度监控器 - 每20秒检查一次checkpoint"""
import json, time, os
from pathlib import Path

d = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3")
ckpt = d / "checkpoint.json"
csv_out = d / "seg_results.csv"

for i in range(120):  # 监控20分钟
    if ckpt.exists():
        try:
            data = json.load(open(ckpt, encoding="utf-8"))
            n = data["count"]
            ok = sum(1 for x in data["done"] if x.get("status") in ("success","partial"))
            print(f"[{i*20}s] progress={n}/136 ok={ok}", flush=True)
        except:
            print(f"[{i*20}s] checkpoint read error", flush=True)
    else:
        print(f"[{i*20}s] no checkpoint yet", flush=True)
    time.sleep(20)
