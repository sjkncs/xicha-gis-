#!/usr/bin/env python3
import json, os, sys, numpy as np

sys.stdout.reconfigure(encoding='utf-8')

RESULT_JSON = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json"
OUT_DIR     = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"
os.makedirs(OUT_DIR, exist_ok=True)

with open(RESULT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

# 重新分析（JSON中已有正确的路径）
# 分类图片所属区域/类型
# 路径格式: /root/autodl-tmp/streetview_analysis/images/{TYPE}/{coords}/filename.jpg
# TYPE 可能是 Village/南山区/宝安区 等

area_map = {}  # name -> stats
for r in data:
    img = r["image"]  # forward slash
    parts = img.split("/")
    # parts: ['', 'root', 'autodl-tmp', 'streetview_analysis', 'images', TYPE, COORDS, filename]
    if len(parts) >= 7:
        area_type = parts[5]  # Village / 南山区 / etc
        coords    = parts[6]  # 113.xxx_yyy
    else:
        area_type = "未知"
        coords = "未知"

    if area_type not in area_map:
        area_map[area_type] = {"imgs": [], "scores": [], "cats": {}, "n_obs": 0}

    area_map[area_type]["imgs"].append(coords)
    area_map[area_type]["scores"].append(r["accessibility_score"])
    area_map[area_type]["n_obs"] += r["total_obstacles"]
    for cat, cnt in r["categories"].items():
        area_map[area_type]["cats"][cat] = area_map[area_type]["cats"].get(cat, 0) + cnt

# 全局统计
all_scores = [r["accessibility_score"] for r in data]
all_cats   = {}
for r in data:
    for cat, cnt in r["categories"].items():
        all_cats[cat] = all_cats.get(cat, 0) + cnt

total_obs = sum(r["total_obstacles"] for r in data)
n_high = sum(1 for s in all_scores if s >= 40)  # 障碍较多

# 生成 Markdown 报告
lines = []
lines.append("# YOLO障碍物检测报告")
lines.append("")
lines.append("**模型**: YOLO11x (COCO基线)")
lines.append("**检测类别**: 行人、汽车占道、自行车占道、摩托车/电动车、公交车占道、货车占道、长椅占道、停车标志")
lines.append("**可信度阈值**: 0.35")
lines.append("**综合评分**: 障碍物conf × 类别权重 × 区域权重(脚边0.5/中部0.35/顶部0.15) × 10，范围0-100")
lines.append("")
lines.append("## 总览")
lines.append("")
lines.append(f"| 指标 | 数值 |")
lines.append(f"|------|------|")
lines.append(f"| 图片总数 | {len(data)} |")
lines.append(f"| 总检测障碍数 | {total_obs} |")
lines.append(f"| 平均评分 | {np.mean(all_scores):.1f} |")
lines.append(f"| 评分中位数 | {np.median(all_scores):.1f} |")
lines.append(f"| 评分范围 | {min(all_scores):.0f} - {max(all_scores):.1f} |")
lines.append(f"| 标准差 | {np.std(all_scores):.1f} |")
lines.append(f"| 障碍较多(>=40分)图片 | {n_high}张 ({n_high/len(data)*100:.1f}%) |")
lines.append(f"| 障碍极少(0分)图片 | {sum(1 for s in all_scores if s==0)}张 |")
lines.append("")
lines.append("## 全局障碍类别统计")
lines.append("")
total_d = sum(all_cats.values())
lines.append(f"| 类别 | 数量 | 占比 |")
lines.append(f"|------|------|------|")
for cat, cnt in sorted(all_cats.items(), key=lambda x: -x[1]):
    lines.append(f"| {cat} | {cnt} | {cnt/total_d*100:.1f}% |")
lines.append("")
lines.append("## 评分区间分布")
lines.append("")
lines.append(f"| 区间 | 评级 | 图片数 | 占比 |")
lines.append(f"|------|------|------|------|")
bins = [(0,10,"畅通"),(10,20,"较畅通"),(20,40,"一般"),(40,60,"较困难"),(60,80,"困难"),(80,100,"严重")]
for lo,hi,label in bins:
    cnt = sum(1 for s in all_scores if lo<=s<hi)
    lines.append(f"| {lo}-{hi} | {label} | {cnt} | {cnt/len(data)*100:.1f}% |")
lines.append("")
lines.append("## 分区域统计")
lines.append("")
lines.append(f"| 区域类型 | 图片数 | 平均评分 | 最高评分 | 障碍总数 |")
lines.append(f"|------|------|------|------|------|")
for area, info in sorted(area_map.items(), key=lambda x: -np.mean(x[1]["scores"])):
    ms = np.mean(info["scores"])
    mx = max(info["scores"])
    lines.append(f"| {area} | {len(info['imgs'])} | {ms:.1f} | {mx:.1f} | {info['n_obs']} |")
lines.append("")
lines.append("## 分区域障碍类别")
lines.append("")
for area, info in sorted(area_map.items(), key=lambda x: -np.mean(x[1]["scores"])):
    lines.append(f"### {area}")
    lines.append("")
    lines.append(f"| 类别 | 数量 |")
    lines.append(f"|------|------|")
    for cat, cnt in sorted(info["cats"].items(), key=lambda x: -x[1]):
        lines.append(f"| {cat} | {cnt} |")
    lines.append("")

report = "\n".join(lines)
with open(f"{OUT_DIR}/YOLO_obstacle_report.md", "w", encoding="utf-8") as f:
    f.write(report)

print(report)
print(f"\nReport saved: {OUT_DIR}/YOLO_obstacle_report.md")
