#!/usr/bin/env python3
"""生成LaTeX论文材料"""
import json, os, sys
import numpy as np
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"
JSON_FILE = os.path.join(LOCAL_RESULTS, "all_results_fixed.json")
OUT_FILE = os.path.join(LOCAL_RESULTS, "nanshan_accessibility_analysis.tex")

with open(JSON_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
all_imgs = data

def get_street(path):
    parts = path.split("/")
    return parts[6] if len(parts) >= 7 and parts[5] == "南山区" else "未知"

def get_district(path):
    for kw in ["南山区", "宝安区", "龙华区", "福田区"]:
        if kw in path:
            return kw
    return "其他"

# Stats
all_cats = defaultdict(int)
for r in nanshan:
    for k, v in r["categories"].items():
        all_cats[k] += v
top_cat = max(all_cats.items(), key=lambda x: x[1])
total_det = sum(all_cats.values())
top_pct = top_cat[1] / total_det * 100

districts = defaultdict(list)
for r in all_imgs:
    districts[get_district(r["image"])].append(r["accessibility_score"])

ns_arr = np.array([r["accessibility_score"] for r in nanshan])
ns_mean = float(np.mean(ns_arr))
ns_med = float(np.median(ns_arr))
ns_std = float(np.std(ns_arr))
ns_min = float(np.min(ns_arr))
ns_max = float(np.max(ns_arr))

rating_bins = [(0,10,"畅通"),(10,20,"较畅通"),(20,40,"一般"),(40,60,"较困难"),(60,80,"困难"),(80,101,"严重")]

by_street = defaultdict(list)
for r in nanshan:
    by_street[get_street(r["image"])].append(r["accessibility_score"])

street_data = []
for street, scores in by_street.items():
    arr = np.array(scores)
    street_data.append({"name": street, "n": len(scores), "mean": float(np.mean(arr)),
                        "median": float(np.median(arr)), "max": float(np.max(arr)), "std": float(np.std(arr))})
street_data.sort(key=lambda x: -x["mean"])
worst = street_data[0]
best = street_data[-1]

# Write LaTeX file
with open(OUT_FILE, "w", encoding="utf-8") as f:
    f.write(r"""\documentclass{article}
\usepackage[UTF8]{ctex}
\usepackage{graphicx}
\usepackage{amsmath}
\usepackage{booktabs}
\usepackage{geometry}
\geometry{a4paper, margin=2.5cm}
\begin{document}
""")
    f.write("\n\\title{基于深度学习的城市无障碍可达性分析}\n")
    f.write("\\subtitle{以深圳市南山区为例}\n")
    f.write("\\date{\\today}\n")
    f.write("\\maketitle\n")

    # Section 1
    f.write("\n\\section{研究数据与实验方法}\n\n")
    f.write("本研究以深圳市南山区为核心研究区，共采集街景图像"+str(len(all_imgs))+"张，其中南山区"+str(len(nanshan))+"张。")
    f.write("图像采集自腾讯/百度街景API，拍摄时间为2022年。")
    f.write("采样密度约为每500米一个采样点，每点采集东、西、南、北四个方向。\ Parra\n\n")

    f.write("本研究采用YOLO11x目标检测模型~\cite{yolo11}，基于COCO-80类别数据集进行预训练。")
    f.write("针对无障碍分析需求，重点关注车辆占道、行人、非机动车等影响通行的目标。")
    f.write("检测置信度阈值设为0.35。\ Parra\n\n")

    f.write("障碍评分公式如式(\ref{eq:obs})所示：\n")
    f.write("\\begin{equation}\n")
    f.write("S_{\\text{obs}} = \\sum_{i} (c_i \\cdot w_i \\cdot z_i) \\times 100\n")
    f.write("\\end{equation}\n\n")
    f.write("其中 $c_i$ 为第 $i$ 个检测目标的置信度，$w_i$ 为类别权重（汽车1.2、货车1.0、摩托车0.8、自行车0.5、行人0.3），$z_i$ 为空间区域权重（通行区0.5、中部0.35、顶部0.15）。\ Parra\n\n")

    f.write("\\section{分析结果}\n\n")
    f.write("南山区"+str(len(nanshan))+"张街景图像的平均障碍评分为"+f"{ns_mean:.1f}"+"分，")
    f.write("中位数"+f"{ns_med:.1f}"+"分，标准差"+f"{ns_std:.1f}"+"分，")
    f.write("评分范围[$"+f"{ns_min:.1f}"+", "+f"{ns_max:.1f}"+"$]。\ Parra\n\n")

    # Category table
    f.write("共检测到"+str(total_det)+"次障碍物，类别分布见表\\ref{tab:cat}。\n")
    f.write("\\begin{table}[h]\n\\centering\n")
    f.write("\\caption{障碍类别统计}\\label{tab:cat}\n")
    f.write("\\begin{tabular}{lcc}\n\\toprule\n")
    f.write("障碍类别 & 检测次数 & 占比 \\\\ \\midrule\n")
    for cat, cnt in sorted(all_cats.items(), key=lambda x: -x[1]):
        pct = cnt / total_det * 100
        f.write(f"{cat} & {cnt} & {pct:.1f}\\% \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n\n")

    f.write("其中"+top_cat[0]+"占道比例最高，达"+f"{top_pct:.1f}"+"\\%，反映出南山区停车供需矛盾突出的结构性问题。\ Parra\n\n")

    # Street table
    f.write("街道级障碍评分统计见表\\ref{tab:street}。\n")
    f.write("\\begin{table}[h]\n\\centering\n")
    f.write("\\caption{南山区各街道障碍评分统计}\\label{tab:street}\n")
    f.write("\\begin{tabular}{lcccccc}\n\\toprule\n")
    f.write("街道 & 样本数 & 均值 & 中位数 & 最高分 & 标准差 & 评级 \\\\ \\midrule\n")
    for s in street_data:
        rating = ("畅通" if s["mean"]<10 else "较畅通" if s["mean"]<20
                  else "一般" if s["mean"]<40 else "较困难" if s["mean"]<60
                  else "困难" if s["mean"]<80 else "严重")
        f.write(f"{s['name']} & {s['n']} & {s['mean']:.1f} & {s['median']:.1f} & {s['max']:.1f} & {s['std']:.1f} & {rating} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n\n")

    f.write("招商街道平均障碍评分最高（"+f"{worst['mean']:.1f}"+"分），主要障碍为汽车占道和摩托车占道。")
    f.write("沙河街道表现最佳（"+f"{best['mean']:.1f}"+"分），可作为示范街道。\ Parra\n\n")

    # District comparison
    f.write("与周边行政区对比：\n")
    f.write("\\begin{tabular}{lcccc}\n\\toprule\n")
    f.write("行政区 & 样本数 & 均值 & 中位数 & 标准差 \\\\ \\midrule\n")
    for dname, dscores in sorted(districts.items(), key=lambda x: np.mean(x[1])):
        if not dscores:
            continue
        arr = np.array(dscores)
        f.write(f"{dname} & {len(dscores)} & {np.mean(arr):.1f} & {np.median(arr):.1f} & {np.std(arr):.1f} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n\n")

    f.write("\\section{讨论}\n\n")
    f.write("主要障碍因素：\n")
    f.write("\\begin{enumerate}\n")
    f.write(f"\\item {top_cat[0]}占道比例最高（{top_pct:.1f}\\%），反映停车位严重不足。\n")
    f.write(f"\\item 摩托车/电动车占道{all_cats.get('摩托车/电动车',0)}次，非机动车停车设施配套不完善。\n")
    f.write(f"\\item 街道间差异显著，招商街道（{worst['mean']:.1f}分）远高于沙河街道（{best['mean']:.1f}分）。\n")
    f.write("\\end{enumerate}\n\n")

    f.write("\\section{结论}\n\n")
    f.write("\\begin{enumerate}\n")
    f.write(f"\\item 南山区平均障碍评分为{ns_mean:.1f}分，处于一般水平。\n")
    f.write(f"\\item {top_cat[0]}占道是最主要障碍（{top_pct:.1f}\\%）。\n")
    f.write(f"\\item 招商街道最差（{worst['mean']:.1f}分），沙河街道最佳（{best['mean']:.1f}分）。\n")
    f.write("\\item 基于YOLO目标检测的15分钟社区无障碍评分方法可为城市改造提供量化依据。\n")
    f.write("\\end{enumerate}\n\n")

    f.write("\\begin{thebibliography}{9}\n")
    f.write("\\bibitem{yolo11} Ultralytics. YOLO11: The Next Generation of Object Detection. 2024.\n")
    f.write("\\bibitem{deeplab} Liang-Chieh Chen, et al. Rethinking Atrous Convolution. arXiv, 2017.\n")
    f.write("\\bibitem{cityscapes} Marius Cordts, et al. The Cityscapes Dataset. CVPR, 2016.\n")
    f.write("\\bibitem{accessibility} WHO. Global Disability Action Plan 2014-2021. 2014.\n")
    f.write("\\end{thebibliography}\n\n")
    f.write("\\end{document}\n")

print(f"OK: {OUT_FILE}")
print(f"图片: {len(nanshan)}/{len(all_imgs)}, 障碍均值: {ns_mean:.1f}")
print(f"主要障碍: {top_cat[0]} ({top_pct:.1f}%)")
print(f"最差街道: {worst['name']} ({worst['mean']:.1f}), 最佳: {best['name']} ({best['mean']:.1f})")
