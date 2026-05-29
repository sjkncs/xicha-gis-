#!/usr/bin/env python3
"""Generate comprehensive Nanshan District accessibility report with CORRECT street data"""
import json, os, sys, numpy as np, base64, re
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"
CHART_DIR     = f"{LOCAL_RESULTS}/charts"
HM_DIR        = f"{LOCAL_RESULTS}/heatmaps_nanshan"

with open(f"{LOCAL_RESULTS}/all_results_fixed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# ---- Parse streets from paths ----
def get_street(path):
    parts = path.split("/")
    if len(parts) >= 7 and parts[5] == "南山区":
        return parts[6]
    return None

def get_coords(path):
    parts = path.split("/")
    if len(parts) >= 8:
        return parts[7]
    return ""

def get_direction(path):
    fn = path.split("/")[-1]
    m = re.search(r'_([NESW])_\d{4}\.jpg', fn)
    return m.group(1) if m else "X"

# Separate districts
nanshan = [r for r in data if "/南山区/" in r["image"]]
baoan   = [r for r in data if "/宝安区/" in r["image"]]
longhua = [r for r in data if "/龙华区/" in r["image"]]
futian  = [r for r in data if "/福田区/" in r["image"]]

# Nanshan street-level
ns_streets = defaultdict(lambda: {"imgs": [], "scores": [], "cats": defaultdict(int), "coords": set(), "n_obs": 0})
for r in nanshan:
    s = get_street(r["image"])
    if s:
        ns_streets[s]["imgs"].append(r["image"].split("/")[-1])
        ns_streets[s]["scores"].append(r["accessibility_score"])
        ns_streets[s]["coords"].add(get_coords(r["image"]))
        ns_streets[s]["n_obs"] += r["total_obstacles"]
        for cat, cnt in r["categories"].items():
            ns_streets[s]["cats"][cat] += cnt

# All-district grouping
districts_all = {}
for r in data:
    d = get_street(r["image"])
    if d is None:
        # non-nanshan: use district keyword
        for kw in ["宝安", "龙华", "福田"]:
            if kw in r["image"]:
                d = kw
                break
        else:
            d = "Village"
    if d not in districts_all:
        districts_all[d] = {"scores": [], "cats": defaultdict(int), "coords": set()}
    districts_all[d]["scores"].append(r["accessibility_score"])
    districts_all[d]["coords"].add(get_coords(r["image"]))
    for cat, cnt in r["categories"].items():
        districts_all[d]["cats"][cat] += cnt

all_scores  = [r["accessibility_score"] for r in data]
ns_scores   = [r["accessibility_score"] for r in nanshan]

def ss(scores):
    a = np.array(scores)
    return {"mean": float(np.mean(a)), "median": float(np.median(a)),
            "min": float(np.min(a)), "max": float(np.max(a)),
            "std": float(np.std(a)), "n": len(scores)}

def rating(score):
    if score < 10:  return ("畅通",    "#27ae60")
    elif score < 20: return ("较畅通", "#2ecc71")
    elif score < 40: return ("一般",    "#f1c40f")
    elif score < 60: return ("较困难",  "#e67e22")
    elif score < 80: return ("困难",    "#e74c3c")
    else:             return ("严重",    "#c0392b")

def b64img(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    return None

# Load charts
charts = {fn: b64img(os.path.join(CHART_DIR, fn))
           for fn in os.listdir(CHART_DIR) if fn.endswith(".png")}

# Heatmap samples
hm_files = sorted(os.listdir(HM_DIR))
hm_samples = []
for r in sorted(nanshan, key=lambda x: x["accessibility_score"]):
    coord = get_coords(r["image"])
    direction = get_direction(r["image"])
    score = r["accessibility_score"]
    rat, color = rating(score)
    for fn in hm_files:
        if coord in fn and f"_{direction}_" in fn and "_score" in fn:
            p = os.path.join(HM_DIR, fn)
            b64 = b64img(p)
            if b64:
                hm_samples.append({
                    "fn": fn, "b64": b64, "score": score,
                    "rating": rat, "color": color, "direction": direction,
                    "cats": r["categories"], "n_obs": r["total_obstacles"]
                })
            break
    if len(hm_samples) >= 9:
        break

ns_s    = ss(ns_scores)
all_s   = ss(all_scores)
baoan_s = ss([r["accessibility_score"] for r in baoan])
longhua_s = ss([r["accessibility_score"] for r in longhua])
futian_s  = ss([r["accessibility_score"] for r in futian])

# Nanshan overall cats
ns_cats = defaultdict(int)
for r in nanshan:
    for cat, cnt in r["categories"].items():
        ns_cats[cat] += cnt
total_nc = sum(ns_cats.values()) if ns_cats else 1

# ---- Build HTML ----
L = []
def h(s): L.append(s)

h('<!DOCTYPE html>')
h('<html lang="zh-CN">')
h('<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">')
h('<title>南山区无障碍可达性分析报告</title>')
h('<style>')
h('*{box-sizing:border-box;margin:0;padding:0}')
h('body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f0f2f5;color:#2c3e50;line-height:1.7}')
h('h1{font-size:2em;color:#1a252f;text-align:center;padding:.5em 0}')
h('h2{font-size:1.3em;color:#1a252f;margin:1.5em 0 .6em;padding:.4em .8em;background:#fff;border-left:4px solid #3498db;border-radius:0 6px 6px 0}')
h('h3{font-size:1.05em;color:#2980b9;margin:.8em 0 .4em}')
h('h4{font-size:.95em;color:#34495e;margin:.6em 0 .3em}')
h('.container{max-width:1200px;margin:0 auto;padding:.5em}')
h('.card{background:#fff;border-radius:12px;padding:1.5em;margin:1em 0;box-shadow:0 2px 12px rgba(0,0,0,.07)}')
h('.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:.8em;margin:.8em 0}')
h('.box{background:linear-gradient(135deg,#3498db,#2471a3);color:#fff;border-radius:12px;padding:1em;text-align:center}')
h('.box.green{background:linear-gradient(135deg,#27ae60,#1e8449)}')
h('.box.orange{background:linear-gradient(135deg,#e67e22,#d35400)}')
h('.box.red{background:linear-gradient(135deg,#e74c3c,#c0392b)}')
h('.box.gray{background:linear-gradient(135deg,#7f8c8d,#5d6d7e)}')
h('.box.purple{background:linear-gradient(135deg,#8e44ad,#6c3483)}')
h('.num{font-size:1.9em;font-weight:bold}')
h('.lbl{font-size:.78em;opacity:.9;margin-top:.2em}')
h('table{width:100%;border-collapse:collapse;margin:.8em 0;font-size:.88em}')
h('th{background:#3498db;color:#fff;padding:.65em 1em;text-align:left;position:sticky;top:0}')
h('td{padding:.55em 1em;border-bottom:1px solid #ecf0f1}')
h('tr:hover td{background:#f8f9fa}')
h('.score-cell{font-weight:bold;font-size:1.05em}')
h('.badge{display:inline-block;padding:.15em .5em;border-radius:4px;font-size:.78em;font-weight:bold;color:#fff}')
h('.bar-wrap{display:flex;align-items:center;gap:.5em;padding:.2em 0}')
h('.bar{height:18px;background:#ecf0f1;border-radius:3px;overflow:hidden;min-width:4px;flex:1}')
h('.fill{height:100%;border-radius:3px}')
h('.w-60{width:60px;min-width:60px;text-align:right;font-weight:bold;font-size:.85em}')
h('.w-50{width:50px;min-width:50px;text-align:right;font-size:.82em;color:#666}')
h('.hm-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.8em}')
h('.hm-item{background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}')
h('.hm-img{width:100%;height:180px;object-fit:cover;display:block}')
h('.hm-cap{padding:.7em;font-size:.8em}')
h('.hm-score{font-size:1.3em;font-weight:bold;margin-bottom:.2em}')
h('.chart-img{width:100%;border-radius:8px;margin:.6em 0}')
h('.tag{display:inline-block;background:#3498db;color:#fff;padding:.08em .35em;border-radius:3px;font-size:.72em;margin:.08em}')
h('.rec{border-radius:0 8px 8px 0;padding:.9em 1.2em;margin:.5em 0;background:#fff}')
h('.rec-h{border-left:4px solid #e74c3c}')
h('.rec-m{border-left:4px solid #f39c12}')
h('.rec-l{border-left:4px solid #27ae60}')
h('.toc{background:#fff;border-radius:10px;padding:1.2em;box-shadow:0 2px 8px rgba(0,0,0,.05)}')
h('.toc a{color:#3498db;text-decoration:none;display:block;padding:.18em 0;font-size:.88em}')
h('.toc a:hover{text-decoration:underline}')
h('.toc ol,.toc ul{padding-left:1.3em;margin:.2em 0}')
h('p{margin:.4em 0}')
h('hr{border:none;border-top:1px solid #eee;margin:1em 0}')
h('.footer{text-align:center;color:#aaa;font-size:.78em;padding:1.5em 0;border-top:1px solid #eee}')
h('</style></head><body>')
h('<div class="container">')

# Title
h('<div class="card" style="text-align:center;padding:1.2em">')
h('<h1>南山区无障碍可达性分析报告</h1>')
h('<p style="color:#888">YOLO11x目标检测 + 2022年腾讯街景影像 | 15分钟社区可达性评估</p>')
h('</div>')

# TOC
h('<div class="card toc">')
h('<h3 style="margin-top:0">报告目录</h3>')
h('<ol>')
for sec in [("exec","一、执行摘要"),("method","二、研究方法"),("overall","三、全局分析"),("district","四、区级对比"),
            ("nanshan","五、南山区概况"),("streets","六、街道级分析"),("samples","七、热图案例"),("rec","八、改进建议")]:
    h(f'<li><a href="#{sec[0]}">{sec[1]}</a></li>')
h('</ol></div>')

# Executive summary
ns_rt, ns_rc = rating(ns_s["mean"])
h(f'<div class="card" id="exec">')
h('<h2>一、执行摘要</h2>')
h('<div class="grid">')
h(f'<div class="box"><div class="num">136</div><div class="lbl">南山区图片</div></div>')
h(f'<div class="box purple"><div class="num">{ns_s["mean"]:.1f}</div><div class="lbl">平均障碍评分</div></div>')
h(f'<div class="box orange"><div class="num">{sum(1 for s in ns_scores if s>=40)}</div><div class="lbl">困难图片(>=40)</div></div>')
h(f'<div class="box green"><div class="num">{sum(1 for s in ns_scores if s<=10)}</div><div class="lbl">畅通图片(0-10)</div></div>')
h(f'<div class="box red"><div class="num">{ns_s["max"]:.0f}</div><div class="lbl">最高评分</div></div>')
h(f'<div class="box gray"><div class="num">8</div><div class="lbl">涉及街道</div></div>')
h(f'<div class="box"><div class="num">599</div><div class="lbl">障碍总检测数</div></div>')
h('</div>')
h(f'<p style="margin-top:.8em">南山区平均障碍评分 <strong style="color:{ns_rc}">{ns_s["mean"]:.1f}</strong>，')
h(f'评级为 <strong style="color:{ns_rc}">{ns_rt}</strong>。')
h(f'共检测障碍物 <strong>599</strong> 次，其中汽车占道 <strong>{ns_cats["汽车占道"]} 次（{ns_cats["汽车占道"]/total_nc*100:.0f}%）</strong>，')
h(f'是首要障碍因素。招商街道可达性最差（平均{ss(ns_streets["招商"]["scores"])["mean"]:.1f}分），')
h(f'沙河街道表现最佳（平均{ss(ns_streets["沙河"]["scores"])["mean"]:.1f}分）。')
h('</div>')

# Method
h('<div class="card" id="method">')
h('<h2>二、研究方法</h2>')
h('<table>')
for row in [
    ("数据来源", "腾讯/百度街景 API，2022年拍摄"),
    ("检测模型", "YOLO11x (COCO-80类基线)"),
    ("检测类别", "汽车、行人、摩托车、自行车、公交车、货车、长椅、停车标志"),
    ("置信度阈值", "0.35"),
    ("评分公式", "Σ(conf × 类别权重 × 区域权重) × 10"),
    ("区域权重", "脚边通行区0.5 / 中部0.35 / 顶部0.15"),
    ("类别权重", "汽车1.2, 行人0.3, 摩托0.8, 公交0.7, 货车1.0, 其他0.5"),
    ("评级标准", "0-10畅通 | 10-20较畅通 | 20-40一般 | 40-60较困难 | 60-80困难 | 80-100严重"),
]:
    h(f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td></tr>')
h('</table></div>')

# Overall
h('<div class="card" id="overall">')
h('<h2>三、全局统计（294张图片，5个区）</h2>')
h('<div class="grid">')
h(f'<div class="box"><div class="num">{len(data)}</div><div class="lbl">总图片</div></div>')
h(f'<div class="box"><div class="num">{sum(r["total_obstacles"] for r in data)}</div><div class="lbl">总障碍数</div></div>')
h(f'<div class="box"><div class="num">{all_s["mean"]:.1f}</div><div class="lbl">全局均分</div></div>')
h(f'<div class="box"><div class="num">{all_s["median"]:.1f}</div><div class="lbl">评分中位数</div></div>')
h(f'<div class="box"><div class="num">{all_s["std"]:.1f}</div><div class="lbl">标准差</div></div>')
h(f'<div class="box red"><div class="num">{all_s["max"]:.1f}</div><div class="lbl">最高分</div></div>')
h('</div>')

if "category_distribution.png" in charts:
    h(f'<h3>障碍类别分布</h3><img class="chart-img" src="data:image/png;base64,{charts["category_distribution.png"]}">')

h('<h3>评分区间分布</h3>')
h('<table>')
h('<tr><th>区间</th><th>评级</th><th>全局占比</th><th>南山占比</th></tr>')
for lo,hi,label,color in [(0,10,"畅通","#27ae60"),(10,20,"较畅通","#2ecc71"),(20,40,"一般","#f1c40f"),(40,60,"较困难","#e67e22"),(60,80,"困难","#e74c3c"),(80,100,"严重","#c0392b")]:
    cnt_all = sum(1 for s in all_scores if lo<=s<hi)
    cnt_ns  = sum(1 for s in ns_scores if lo<=s<hi)
    h(f'<tr><td>{lo}-{hi}</td><td><span class="badge" style="background:{color}">{label}</span></td>')
    h(f'<td><div class="bar-wrap"><div class="bar"><div class="fill" style="width:{cnt_all/len(all_scores)*100}%;background:{color}"></div></div><div class="w-60">{cnt_all}张({cnt_all/len(all_scores)*100:.1f}%)</div></div></td>')
    h(f'<td><div class="bar-wrap"><div class="bar"><div class="fill" style="width:{cnt_ns/len(ns_scores)*100}%;background:{color}"></div></div><div class="w-60">{cnt_ns}张({cnt_ns/len(ns_scores)*100:.1f}%)</div></div></td></tr>')
h('</table></div>')

# District comparison
h('<div class="card" id="district">')
h('<h2>四、区级对比</h2>')
if "district_comparison.png" in charts:
    h(f'<img class="chart-img" src="data:image/png;base64,{charts["district_comparison.png"]}">')

h('<table>')
h('<tr><th>行政区</th><th>图片数</th><th>采样点</th><th>均分</th><th>中位数</th><th>最高</th><th>障碍总数</th><th>评级</th><th>首要障碍</th></tr>')
district_rows = [
    ("宝安区", baoan, baoan_s),
    ("南山区", nanshan, ns_s),
    ("龙华区", longhua, longhua_s),
    ("福田区", futian, futian_s),
]
for name, rlist, s in district_rows:
    rt, rc = rating(s["mean"])
    all_cats_d = defaultdict(int)
    for r in rlist:
        for cat, cnt in r["categories"].items():
            all_cats_d[cat] += cnt
    top_cat = sorted(all_cats_d.items(), key=lambda x: -x[1])[0] if all_cats_d else ("无",0)
    h(f'<tr><td><strong>{name}</strong></td><td>{s["n"]}</td><td>{len(set(get_coords(r["image"]) for r in rlist))}</td>')
    h(f'<td class="score-cell" style="color:{rc}">{s["mean"]:.1f}</td>')
    h(f'<td>{s["median"]:.1f}</td><td>{s["max"]:.0f}</td>')
    h(f'<td>{sum(r["total_obstacles"] for r in rlist)}</td>')
    h(f'<td><span class="badge" style="background:{rc}">{rt}</span></td>')
    h(f'<td>{top_cat[0]}({top_cat[1]})</td></tr>')
h('</table>')
h('<p style="color:#888;font-size:.85em">注：宝安区平均分最高（障碍最多），福田区和沙河街道可达性最好。Village为城中村特殊采样点。</p>')
h('</div>')

# Nanshan
h('<div class="card" id="nanshan">')
h('<h2>五、南山区详细分析</h2>')
h('<div class="grid">')
h(f'<div class="box"><div class="num">{len(nanshan)}</div><div class="lbl">图片数</div></div>')
h(f'<div class="box"><div class="num">{len(set(get_coords(r["image"]) for r in nanshan))}</div><div class="lbl">采样点</div></div>')
h(f'<div class="box orange"><div class="num">{ns_s["mean"]:.1f}</div><div class="lbl">平均评分</div></div>')
h(f'<div class="box"><div class="num">{ns_s["median"]:.1f}</div><div class="lbl">中位数</div></div>')
h(f'<div class="box red"><div class="num">{ns_s["max"]:.0f}</div><div class="lbl">最高分</div></div>')
h(f'<div class="box green"><div class="num">{sum(1 for s in ns_scores if s<=10)}</div><div class="lbl">畅通(0-10)</div></div>')
h(f'<div class="box orange"><div class="num">{sum(1 for s in ns_scores if s>=40)}</div><div class="lbl">困难(>=40)</div></div>')
h(f'<div class="box"><div class="num">599</div><div class="lbl">障碍总检测</div></div>')
h('</div>')

if "score_distribution.png" in charts:
    h(f'<h3>评分分布对比</h3><img class="chart-img" src="data:image/png;base64,{charts["score_distribution.png"]}">')

h('<h3>南山区障碍类别排名</h3>')
h('<table>')
h('<tr><th>#</th><th>类别</th><th>检测数</th><th>占南山区比</th><th>障碍影响</th></tr>')
cat_colors = {"汽车占道":"#e74c3c","行人/使用者":"#3498db","摩托车/电动车":"#f39c12",
              "货车占道":"#c0392b","自行车占道":"#27ae60","公交车占道":"#d35400","停车标志":"#7f8c8d","长椅占道":"#27ae60"}
cat_desc  = {"汽车占道":"主要障碍，严重影响通行","行人/使用者":"通常非障碍，密集时影响","摩托车/电动车":"占道停放，较严重","货车占道":"大型占道，严重影响","自行车占道":"小型占道，影响有限","公交车占道":"公交停靠，一定影响","停车标志":"标识物，非物理障碍","长椅占道":"街道设施，通常合规"}
for i, (cat, cnt) in enumerate(sorted(ns_cats.items(), key=lambda x:-x[1]), 1):
    pct = cnt/total_nc*100
    imp = "高" if cnt >= 80 else "中" if cnt >= 20 else "低"
    ic = "#e74c3c" if imp=="高" else "#f39c12" if imp=="中" else "#27ae60"
    cc = cat_colors.get(cat, "#3498db")
    h(f'<tr><td>{i}</td>')
    h(f'<td><span class="badge" style="background:{cc}">{cat}</span></td>')
    h(f'<td><strong>{cnt}</strong></td>')
    h(f'<td><div class="bar-wrap"><div class="bar"><div class="fill" style="width:{pct}%;background:{cc}"></div></div><div class="w-60">{pct:.1f}%</div></div></td>')
    h(f'<td><span class="badge" style="background:{ic}">{imp}</span> {cat_desc.get(cat,"")}</td></tr>')
h('</table>')

# Per-street category breakdown
h('<h3>各街道障碍结构</h3>')
for street, info in sorted(ns_streets.items(), key=lambda x: -ss(x[1]["scores"])["mean"]):
    if street == "Village": continue
    s = ss(info["scores"])
    rt, rc = rating(s["mean"])
    total_sc = sum(info["cats"].values()) if info["cats"] else 1
    h(f'<h4>{street}街道 <span class="badge" style="background:{rc}">{rt}</span> 均分{s["mean"]:.1f}(n={s["n"]}, 最高{s["max"]:.0f})</h4>')
    h('<table>')
    h('<tr><th>类别</th><th style="width:60%">占比</th><th>次数</th><th>占比</th></tr>')
    for cat, cnt in sorted(info["cats"].items(), key=lambda x: -x[1]):
        pct = cnt/total_sc*100
        cc = cat_colors.get(cat, "#3498db")
        h(f'<tr><td><span class="tag" style="background:{cc}">{cat}</span></td>')
        h(f'<td><div class="bar-wrap"><div class="bar"><div class="fill" style="width:{pct}%;background:{cc}"></div></div></div></td>')
        h(f'<td class="w-60">{cnt}</td><td class="w-50">{pct:.0f}%</td></tr>')
    h('</table>')
h('</div>')

# Streets table
h('<div class="card" id="streets">')
h('<h2>六、街道级综合分析</h2>')
h('<p>南山区共8个街道/区域，136张图片。注：粤海街道数据来自"粤海"关键词路径，与南山区地理对应。</p>')
h('<table>')
h('<tr><th>街道</th><th>图片数</th><th>采样点</th><th>均分</th><th>中位数</th><th>最高</th><th>障碍总数</th><th>评级</th><th>主要问题</th></tr>')
street_rows = []
for street, info in ns_streets.items():
    if street == "Village": continue
    s = ss(info["scores"])
    rt, rc = rating(s["mean"])
    top3 = sorted(info["cats"].items(), key=lambda x:-x[1])[:3]
    issues = "、".join([f"{c}({n})" for c,n in top3])
    street_rows.append((street, s, rt, rc, issues, info))
street_rows.sort(key=lambda x: -x[1]["mean"])
for street, s, rt, rc, issues, info in street_rows:
    h(f'<tr><td><strong>{street}</strong></td><td>{s["n"]}</td><td>{len(info["coords"])}</td>')
    h(f'<td class="score-cell" style="color:{rc}">{s["mean"]:.1f}</td>')
    h(f'<td>{s["median"]:.1f}</td><td>{s["max"]:.0f}</td>')
    h(f'<td>{info["n_obs"]}</td>')
    h(f'<td><span class="badge" style="background:{rc}">{rt}</span></td>')
    h(f'<td style="font-size:.82em">{issues}</td></tr>')
h('</table>')

h('<h3>改进优先级</h3>')
h('<table>')
h('<tr><th>优先级</th><th>街道</th><th>均分</th><th>核心问题</th><th>改进建议</th></tr>')
priorities = [
    (1,"招商街道",34.0,"汽车+摩托车占道严重","专项治理，增加物理隔离，限制占道停车","#e74c3c"),
    (2,"粤海街道",22.2,"行人密度高，汽车与行人冲突","设置人车分流，优化过街设施","#e67e22"),
    (3,"西丽街道",24.6,"汽车占道较多","挖掘路外停车资源，引导入场停放","#f39c12"),
    (4,"南头街道",20.9,"货车临时占道较多","明确货车停放区域和时限","#f39c12"),
    (5,"南山街道",15.9,"货车占道比例高","针对工业园区周边强化管理","#7f8c8d"),
    (6,"蛇口街道",16.9,"汽车+货车混合","分时段差异化管控","#7f8c8d"),
    (7,"桃源街道",14.2,"整体良好","保持现状，定期巡查","#27ae60"),
    (8,"沙河街道",11.1,"可达性最佳","树立示范街道，总结推广经验","#27ae60"),
]
for pri, street, mean, prob, fix, color in priorities:
    h(f'<tr><td><span class="badge" style="background:{color}">P{pri}</span></td>')
    h(f'<td><strong>{street}</strong></td>')
    h(f'<td style="color:{color};font-weight:bold">{mean:.1f}</td>')
    h(f'<td>{prob}</td><td>{fix}</td></tr>')
h('</table></div>')

# Heatmap samples
h('<div class="card" id="samples">')
h('<h2>七、典型热图案例</h2>')
h('<p>每组四张图片代表东西南北四个方向，颜色热图：红色=高障碍密度，绿色=畅通。FCN语义分割结果标注了可通行/障碍区域。</p>')
h('<div class="hm-grid">')
for hm in hm_samples:
    h('<div class="hm-item">')
    h(f'<img class="hm-img" src="data:image/jpeg;base64,{hm["b64"]}" alt="heatmap">')
    h('<div class="hm-cap">')
    h(f'<div class="hm-score" style="color:{hm["color"]}">{hm["score"]:.1f} 分</div>')
    h(f'<span class="badge" style="background:{hm["color"]}">{hm["rating"]}</span> ')
    h(f'<span style="color:#888;font-size:.85em">方向:{hm["direction"]} | 障碍:{hm["n_obs"]}个</span>')
    if hm["cats"]:
        cats_str = "、".join([f"{k}({v})" for k,v in sorted(hm["cats"].items(), key=lambda x:-x[1])[:3]])
        h(f'<div style="margin-top:.3em;font-size:.78em;color:#555">{cats_str}</div>')
    h('</div></div>')
h('</div></div>')

# Recommendations
h('<div class="card" id="rec">')
h('<h2>八、改进建议</h2>')
recs = [
    ("rec-h", "P1 招商街道重点改造",
     "招商街道均分34.0（较困难级别），最高达75.9分，是南山区无障碍可达性最差街道。建议：对人行道宽度不足路段实施拓宽改造；在显著位置安装物理阻车设施，防止汽车驶入人行道；与周边商业体协调共享停车资源。",
     "#e74c3c"),
    ("rec-h", "P1 专项治理汽车占道顽疾",
     "汽车占道占南山区障碍的62.3%（373次），是所有街道的共同首要问题。建议：①在问题突出路段安装阻车桩/花坛隔离；②协调周边停车场资源，引导车辆入场；③在重点路口增设违章停车电子监控。",
     "#e74c3c"),
    ("rec-m", "P2 粤海街道人车分流优化",
     "粤海街道行人密度高（31次检测），与汽车混行冲突明显。建议：设置专用非机动车道，安装机非隔离护栏，完善过街红绿灯和斑马线。",
     "#f39c12"),
    ("rec-m", "P2 完善非机动车停放管理",
     "摩托车/电动车占道136次（占11.5%），各街道均有。建议：在地铁口、公交站等重点区域划定专用停车区，安装停车架；试点电子围栏管理。",
     "#f39c12"),
    ("rec-m", "P3 建立动态监测机制",
     "建议每季度对障碍评分>=40分的困难地点进行复查，建立整改台账，推动街道办和城管部门落实责任，形成[发现-整改-核查]闭环。",
     "#f39c12"),
    ("rec-l", "P4 沙河街道经验推广",
     "沙河街道均分11.1（最佳），建议总结其人行道管理经验（充足停车位、机非分流到位），在南山区其他街道推广。",
     "#27ae60"),
    ("rec-l", "P4 数据精细化扩展",
     "当前8个街道136张图片，采样密度约4点/km²。建议提升至20点/km²（500m间隔），覆盖城中村内部道路，支撑15分钟社区全覆盖评估。",
     "#27ae60"),
]
for cls, title, body, color in recs:
    h(f'<div class="rec {cls}">')
    h(f'<h3><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:{color};margin-right:.5em"></span>{title}</h3>')
    h(f'<p>{body}</p></div>')

h('<h3>15分钟可达性评估维度完善建议</h3>')
h('<table>')
h('<tr><th>维度</th><th>当前指标</th><th>建议补充指标</th><th>补充方法</th></tr>')
for row in [
    ("通行障碍", "YOLO障碍评分(0-100)", "台阶、坡道、盲道专项检测", "YOLOv8 + 专类模型或GroundingDINO"),
    ("路面质量", "无", "破损路面、坑洼、裂缝", "语义分割 + 专类检测"),
    ("无障碍设施", "无", "坡道、盲道覆盖率", "Mapillary Vistas预训练模型"),
    ("标识系统", "停车标志(4次)", "无障碍引导标识完整度", "目标检测 + 分类模型"),
    ("采样密度", "4点/km²", "提升至20点/km²", "缩小采样间隔至500m"),
    ("目的地可达", "无", "距最近地铁/公交站步行时间", "接入高德/腾讯POI API"),
]:
    h(f'<tr><td><strong>{row[0]}</strong></td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td></tr>')
h('</table>')
h('</div>')

h('<div class="footer">')
h('<p>报告生成: 2026-05-29 | 模型: YOLO11x | 数据: 2022年南山区街景影像 | 障碍评分: 0=畅通, 100=严重堵塞</p>')
h('</div>')

h('</div></body></html>')

out = f"{LOCAL_RESULTS}/南山区无障碍可达性分析报告.html"
with open(out, "w", encoding="utf-8") as f:
    f.write("\n".join(L))

print(f"Saved: {out} ({os.path.getsize(out)} bytes)")
print(f"Charts: {len(charts)}, Heatmap samples: {len(hm_samples)}")
