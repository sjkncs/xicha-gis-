# -*- coding: utf-8 -*-
"""快速检查checkpoint结果"""
import json
from pathlib import Path

ckpt = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results\checkpoint.json")
if ckpt.exists():
    data = json.load(open(ckpt, encoding="utf-8"))
    print(f"Checkpoint记录: {data['count']}")
    items = data['done']
    success = [x for x in items if x.get('status') == 'success']
    failed = [x for x in items if x.get('status') != 'success']
    print(f"成功: {len(success)} | 失败: {len(failed)}")

    # 统计
    bld_vals = [x.get('building_pct', 0) for x in success if x.get('building_pct') is not None]
    if bld_vals:
        avg_b = sum(bld_vals) / len(bld_vals)
        print(f"\n已处理20张平均建筑覆盖率: {avg_b:.1f}%")

    # 列出失败的
    if failed:
        print(f"\n失败记录:")
        for f in failed:
            print(f"  {Path(f['path']).name}: {f.get('status')} - {f.get('error', f.get('raw',''))[:80]}")
else:
    print("No checkpoint found")
