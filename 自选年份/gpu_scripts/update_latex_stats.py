#!/usr/bin/env python3
"""提取全量294张图的新统计数字，用于更新LaTeX"""
import json, os, glob, numpy as np

JSON_PATH = r"e:\xicha gis 智能定位\自选年份\all_sim_results.json"
PAPER_FIG = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures"

with open(JSON_PATH, encoding="utf-8") as f:
    results = json.load(f)

print(f"=== 全量分析结果 (N={len(results)}) ===")

# 总体统计
obs = [r["obs_score"] for r in results]
pas = [r["passability"] for r in results]
rrs = [r["road_ratio"] for r in results]
dets = [r["n_dets"] for r in results]

print(f"\n障碍分数: mean={np.mean(obs):.1f} median={np.median(obs):.1f} std={np.std(obs):.1f}")
print(f"  min={np.min(obs):.1f} max={np.max(obs):.1f}")
print(f"  P25={np.percentile(obs,25):.1f} P75={np.percentile(obs,75):.1f} P90={np.percentile(obs,90):.1f}")
print(f"通行率: mean={np.mean(pas):.1%} median={np.median(pas):.1%}")
print(f"道路比: mean={np.mean(rrs):.1%}")
print(f"检测数: mean={np.mean(dets):.1f} median={np.median(dets):.0f}")

# 按方向统计
from collections import defaultdict
by_dir = defaultdict(list)
for r in results:
    by_dir[r["direction"]].append(r)

print(f"\n=== 按方向统计 ===")
for d in ["N","E","S","W"]:
    items = by_dir.get(d, [])
    if items:
        obs_d = [r["obs_score"] for r in items]
        pas_d = [r["passability"] for r in items]
        dets_d = [r["n_dets"] for r in items]
        cnt = len(items)
        print(f"  {d} (n={cnt}): obs={np.mean(obs_d):.1f} pass={np.mean(pas_d):.1%} dets={np.mean(dets_d):.1f}")

# 按障碍等级
high = [r for r in results if r["obs_score"] >= 70]
mid = [r for r in results if 40 <= r["obs_score"] < 70]
low = [r for r in results if r["obs_score"] < 40]
print(f"\n障碍等级: 高(n={len(high)}) 中(n={len(mid)}) 低(n={len(low)})")

# 找出各方向的平均图（用于 directional comparison figure）
print(f"\n=== 各方向代表图 ===")
from collections import Counter
dir_cn = {"N":"北","E":"东","S":"南","W":"西"}
for d in ["N","E","S","W"]:
    items = by_dir.get(d, [])
    if items:
        # 选最接近该方向均值的一张
        obs_d = [r["obs_score"] for r in items]
        mean_obs = np.mean(obs_d)
        best = min(items, key=lambda r: abs(r["obs_score"] - mean_obs))
        print(f"  {d}({dir_cn[d]}): {best['coords']} obs={best['obs_score']:.1f} pass={best['passability']:.1%} n_dets={best['n_dets']}")

# 分类代表图
print(f"\n=== 分类代表图 ===")
high_rep = max(high, key=lambda r: r["obs_score"])
mid_rep = min(mid, key=lambda r: abs(r["obs_score"] - 55))
low_rep = min(low, key=lambda r: r["obs_score"])
print(f"  高: {high_rep['coords']} obs={high_rep['obs_score']:.1f} pass={high_rep['passability']:.1%}")
print(f"  中: {mid_rep['coords']} obs={mid_rep['obs_score']:.1f} pass={mid_rep['passability']:.1%}")
print(f"  低: {low_rep['coords']} obs={low_rep['obs_score']:.1f} pass={low_rep['passability']:.1%}")

# 复制到 paper figures
import shutil
# fig_sim_high_obstacle
src = high_rep["annotated"]
dst = os.path.join(PAPER_FIG, "fig_sim_high_obstacle.jpg")
if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"\n复制 high -> {dst}")

# fig_sim_moderate_obstacle
src = mid_rep["annotated"]
dst = os.path.join(PAPER_FIG, "fig_sim_moderate_obstacle.jpg")
if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"复制 mid -> {dst}")

# fig_sim_low_obstacle
src = low_rep["annotated"]
dst = os.path.join(PAPER_FIG, "fig_sim_low_obstacle.jpg")
if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"复制 low -> {dst}")

# 各方向代表图
from collections import defaultdict
dir_best = {}
for d in ["N","E","S","W"]:
    items = by_dir.get(d, [])
    if items:
        mean_obs = np.mean([r["obs_score"] for r in items])
        best = min(items, key=lambda r: abs(r["obs_score"] - mean_obs))
        dir_best[d] = best
        src = best["annotated"]
        dst = os.path.join(PAPER_FIG, f"fig_sim_{d}.jpg")
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"复制 {d} -> {dst}")

print(f"\n所有代表图已复制到: {PAPER_FIG}")
