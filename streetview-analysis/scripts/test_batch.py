# -*- coding: utf-8 -*-
"""先测试3张，确认流程正确"""
import sys
sys.path.insert(0, r"e:\xicha gis 智能定位\自选年份")

from batch_segmentation import load_images, analyze_one, parse_json_response, RESULTS_CSV, OUT_DIR
from pathlib import Path
import csv, json

tasks = load_images()[:3]
print(f"测试 {len(tasks)} 张...")

results = []
for i, task in enumerate(tasks):
    print(f"\n[{i+1}] {task['path'][-60:]}")
    res = analyze_one(task)
    print(f"    status: {res['status']}")
    if res['status'] == 'success':
        print(f"    建筑:{res['data'].get('building_pct')}% 道路:{res['data'].get('road_pct')}% 绿地:{res['data'].get('green_pct')}%")
        print(f"    城市形态:{res['data'].get('urban_form')}")
    else:
        print(f"    error: {res.get('error', res.get('raw',''))[:100]}")

    row = {"path": task["path"], "status": res["status"]}
    if res["status"] == "success":
        row.update(res["data"])
    results.append(row)

print("\n=== 测试完成 ===")
