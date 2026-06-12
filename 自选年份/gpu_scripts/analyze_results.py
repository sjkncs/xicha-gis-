#!/usr/bin/env python3
"""分析全量结果，选择代表性图片"""
import json, os, glob

LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\annotated_streetview"
JSON_PATH = r"e:\xicha gis 智能定位\自选年份\all_sim_results.json"
PAPER_FIG = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures"

os.makedirs(PAPER_FIG, exist_ok=True)

with open(JSON_PATH, encoding="utf-8") as f:
    results = json.load(f)

print(f"总图片: {len(results)} 张")

# 按障碍分数分类
high = [(r, r["obs_score"]) for r in results if r["obs_score"] >= 70]
mid = [(r, abs(r["obs_score"] - 50)) for r in results if 40 <= r["obs_score"] < 70]
low = [(r, r["obs_score"]) for r in results if r["obs_score"] < 40]

print(f"\n高障碍 (>=70): {len(high)} 张")
print(f"中障碍 (40-70): {len(mid)} 张")
print(f"低障碍 (<40): {len(low)} 张")

# 选代表图（障碍高中低各选典型）
# 按方向分散选
dirs = {"N":[], "E":[], "S":[], "W":[]}
for r in results:
    d = r.get("direction","?")
    if d in dirs:
        dirs[d].append(r)

def pick_best(dlist, label):
    """dlist is list of (r, score) tuples"""
    if not dlist:
        print(f"  [{label}] 无图片")
        return []
    # by_obs: highest obstacle first
    by_obs = sorted(dlist, key=lambda x: -x[0]["obs_score"])
    # by_pass: lowest passability first
    by_pass = sorted(dlist, key=lambda x: x[0]["passability"])
    pics = []
    seen_dirs = set()
    for r, _ in by_obs:
        d = r.get("direction","?")
        if d not in seen_dirs and len(pics) < 4:
            pics.append(r)
            seen_dirs.add(d)
    return pics

high_pics = pick_best(high, "高障碍")
mid_pics = pick_best(mid, "中障碍")
low_pics = pick_best([r for r in low if r[0]["passability"] >= 0.5], "低障碍")
print(f"\n=== 选择代表性图片 ===")
print(f"高障碍示例:")
for r in high_pics:
    print(f"  {r['coords']} [{r['direction']}] obs={r['obs_score']:.1f} pass={r['passability']:.1%} dets={r['n_dets']}")

print(f"\n中障碍示例:")
for r in mid_pics:
    print(f"  {r['coords']} [{r['direction']}] obs={r['obs_score']:.1f} pass={r['passability']:.1%} dets={r['n_dets']}")

print(f"\n低障碍示例:")
for r in low_pics[:4]:
    print(f"  {r['coords']} [{r['direction']}] obs={r['obs_score']:.1f} pass={r['passability']:.1%} dets={r['n_dets']}")

# 复制代表性图片到 paper figures
import shutil
selections = {
    "fig_sim_high_obstacle": high_pics[0] if high_pics else None,
    "fig_sim_moderate_obstacle": mid_pics[0] if mid_pics else None,
    "fig_sim_low_obstacle": low_pics[0] if low_pics else None,
}

print(f"\n=== 复制到论文 figures ===")
for key, r in selections.items():
    if r is None:
        print(f"  {key}: 无数据")
        continue
    src = r["annotated"]
    if not os.path.exists(src):
        print(f"  {key}: 文件不存在 {src}")
        continue
    dst = os.path.join(PAPER_FIG, f"{key}.jpg")
    shutil.copy2(src, dst)
    print(f"  {key}: {r['coords']} -> {dst}")

# 也复制 60 张原始 GPU 样本到 appendix 目录
APPENDIX_DIR = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\appendix_figures"
APPENDIX_RAW = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\appendix_raw"
os.makedirs(APPENDIX_RAW, exist_ok=True)

# 复制全量标注图到 appendix
print(f"\n=== 准备附录材料 ===")
raw_dir = r"e:\xicha gis 智能定位\自选年份\raw_streetview"
annotated_dir = r"e:\xicha gis 智能定位\自选年份\annotated_streetview"

# 全量原图 -> appendix_raw
raw_files = glob.glob(os.path.join(raw_dir, "**", "*.jpg"), recursive=True)
print(f"原图 {len(raw_files)} 张 -> {APPENDIX_RAW}")
for f in raw_files[:5]:  # 只打印前5
    print(f"  {f}")

# 全量标注图 -> appendix_figures
ann_files = glob.glob(os.path.join(annotated_dir, "*.jpg"))
print(f"\n标注图 {len(ann_files)} 张 -> {APPENDIX_DIR}")

# 保存分类好的数据供 LaTeX 使用
cat_results = {"high_obstacle": [r for r,_ in high],
               "moderate_obstacle": [r for r,_ in mid],
               "low_obstacle": [r for r,_ in low]}
cat_json = r"e:\xicha gis 智能定位\自选年份\all_sim_results_categorized.json"
with open(cat_json, "w", encoding="utf-8") as f:
    json.dump(cat_results, f, ensure_ascii=False, indent=2)
print(f"\n分类结果: {cat_json}")
