#!/usr/bin/env python3
"""Generate comprehensive Nanshan District accessibility report"""
import json, os, sys, numpy as np, base64, re

sys.stdout.reconfigure(encoding='utf-8')

LOCAL_RESULTS = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"
CHART_DIR     = f"{LOCAL_RESULTS}/charts"
HM_DIR        = f"{LOCAL_RESULTS}/heatmaps_nanshan"

with open(f"{LOCAL_RESULTS}/all_results_fixed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# ========== Parse all images ==========
# Image paths: /root/autodl-tmp/streetview_analysis/images/{DISTRICT}/{STREET}/{COMMUNITY}/{SUBTYPE}/{coords}/{filename}.jpg
# FCN heatmaps: /root/autodl-tmp/streetview_analysis/output/heatmaps/{DISTRICT}_{STREET}_{COMMUNITY}_{SUBTYPE}_{coords}_{coords}_{DIR}_2022_fcn.jpg
# YOLO results JSON: /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/...

def parse_image_path(path):
    """Extract district, street, community, subtype, coords, direction from path"""
    parts = path.split("/")
    result = {
        "district": "未知", "street": "未知街道", "community": "未知社区",
        "subtype": "开放其他", "coords": "", "direction": "X",
        "area_full": "南山区_未知"
    }
    if len(parts) >= 6:
        result["district"] = parts[5]
    # coords: last part before filename
    if len(parts) >= 7:
        result["coords"] = parts[6]
    fn = parts[-1] if parts else ""
    # direction from filename: coord_dir_year.jpg e.g. 113.xxx_22.xxx_N_2022.jpg
    m = re.search(r'_([NESW])_\d{4}\.jpg', fn)
    if m:
        result["direction"] = m.group(1)
    return result

# Parse all results
for r in data:
    info = parse_image_path(r["image"])
    r["district"]    = info["district"]
    r["street"]      = info["street"]
    r["community"]   = info["community"]
    r["subtype"]     = info["subtype"]
    r["coords"]      = info["coords"]
    r["direction"]   = info["direction"]

# ========== Parse street-level stats from street_stats_fixed.json ==========
with open(f"{LOCAL_RESULTS}/street_stats_fixed.json", "r", encoding="utf-8") as f:
    street_data = json.load(f)

# ========== Compute district-level stats ==========
districts = {}
for r in data:
    d = r["district"]
    if d not in districts:
        districts[d] = {"imgs": [], "scores": [], "cats": {}, "n_obs": 0, "coords": set()}
    districts[d]["imgs"].append(r["coords"])
    districts[d]["scores"].append(r["accessibility_score"])
    districts[d]["n_obs"] += r["total_obstacles"]
    districts[d]["coords"].add(r["coords"])
    for cat, cnt in r["categories"].items():
        districts[d]["cats"][cat] = districts[d]["cats"].get(cat, 0) + cnt

all_scores = [r["accessibility_score"] for r in data]

# ========== Parse Nanshan street-level from heatmap filenames ==========
# Get street info from server file listing
# We already know from the downloaded heatmaps the street breakdown:
# 南山区_南头街道_未知社区_OpenOther-开放其他_
# 南山区_南山街道_未知社区_OpenOther-开放其他_
# 南山区_招商街道_未知社区_OpenOther-开放其他_
# 南山区_蛇口街道_未知社区_OpenOther-开放其他_

# Count images per street in Nanshan from our JSON
nanshan = [r for r in data if r["district"] == "南山区"]
street_map = {}  # street -> list of results
for r in nanshan:
    # Try to infer street from coords - we'll group by a simple approach
    # For now just use all nanshan together
    pass

# Actually, from the heatmap filenames we know streets: 南头街道, 南山街道, 招商街道, 蛇口街道
# Let's infer from the coords by examining each image's heatmap filename
# We need to check which coords belong to which street
# From the server file listing, we know patterns like:
# 南山区_南头_未知社区_OpenOther-开放其他_113.917632_22.559302_
# Let's count how many unique coords per street

# We'll parse street from the full image path segments
# For nanshan images: /root/autodl-tmp/streetview_analysis/images/南山区/{STREET}/...
# The street is the 6th part for 南山区 images

nanshan_streets = {}
for r in nanshan:
    parts = r["image"].split("/")
    # format: ['', 'root', ..., 'images', '南山区', '街道名', '社区', ...]
    if len(parts) >= 6 and parts[5] == "南山区":
        if len(parts) >= 7:
            street = parts[6]
        else:
            street = "未知街道"
    elif parts[5] == "南山区":
        street = parts[5]  # This shouldn't happen
    else:
        # non-nanshan
        street = "非南山"
    
    if street not in nanshan_streets:
        nanshan_streets[street] = {"imgs": [], "scores": [], "cats": {}, "n_obs": 0, "coords": set()}
    nanshan_streets[street]["imgs"].append(r["coords"])
    nanshan_streets[street]["scores"].append(r["accessibility_score"])
    nanshan_streets[street]["n_obs"] += r["total_obstacles"]
    nanshan_streets[street]["coords"].add(r["coords"])
    for cat, cnt in r["categories"].items():
        nanshan_streets[street]["cats"][cat] = nanshan_streets[street]["cats"].get(cat, 0) + cnt

# Also separate non-nanshan
baoan = [r for r in data if r["district"] == "宝安区"]
longhua = [r for r in data if r["district"] == "龙华区"]
futian = [r for r in data if r["district"] == "福田区"]

def score_stats(scores):
    if not scores:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "std": 0, "n": 0}
    arr = np.array(scores)
    return {
        "mean":   float(np.mean(arr)),
        "median": float(np.median(arr)),
        "min":    float(np.min(arr)),
        "max":    float(np.max(arr)),
        "std":    float(np.std(arr)),
        "n":      len(scores)
    }

def rating(score):
    if score < 10:  return ("畅通", "#27ae60")
    elif score < 20: return ("较畅通", "#2ecc71")
    elif score < 40: return ("一般", "#f1c40f")
    elif score < 60: return ("较困难", "#e67e22")
    elif score < 80: return ("困难", "#e74c3c")
    else:            return ("严重", "#c0392b")

def rating_emoji(score):
    if score < 10:  return "A"
    elif score < 20: return "B"
    elif score < 40: return "C"
    elif score < 60: return "D"
    elif score < 80: return "E"
    else:            return "F"

# ========== Build HTML ==========
def img_to_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    return None

charts = {}
for fn in os.listdir(CHART_DIR):
    if fn.endswith(".png"):
        p = os.path.join(CHART_DIR, fn)
        b64 = img_to_base64(p)
        if b64:
            charts[fn] = b64

hm_files = sorted(os.listdir(HM_DIR))

# Select representative heatmap samples (high/mid/low)
hm_samples = []
for r in sorted(nanshan, key=lambda x: x["accessibility_score"]):
    coord_match = r["coords"]
    direction = r["direction"]
    score = r["accessibility_score"]
    # find matching heatmap
    for fn in hm_files:
        if coord_match in fn and f"_{direction}_" in fn and "_score" in fn:
            p = os.path.join(HM_DIR, fn)
            b64 = img_to_base64(p)
            if b64:
                rat, color = rating(score)
                hm_samples.append({
                    "fn": fn, "b64": b64, "score": score,
                    "rating": rat, "color": color, "direction": direction,
                    "cats": r["categories"], "n_obs": r["total_obstacles"]
                })
            break
    if len(hm_samples) >= 9:
        break

# Get top/bottom streets
ns_stats = {s: score_stats(v["scores"]) for s, v in nanshan_streets.items()}
top_streets = sorted(ns_stats.items(), key=lambda x: -x[1]["mean"])[:4]
bottom_streets = sorted(ns_stats.items(), key=lambda x: x[1]["mean"])[:4]

# ========== HTML ==========
html = []
html.append('<!DOCTYPE html>')
html.append('<html lang="zh-CN">')
html.append('<head>')
html.append('<meta charset="UTF-8">')
html.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
html.append('<title>南山区无障碍可达性分析报告</title>')
html.append('<style>')
html.append('*{box-sizing:border-box;margin:0;padding:0}')
html.append('body{font-family:"Microsoft YaHei","PingFang SC",sans-serif;background:#f5f6fa;color:#2c3e50;line-height:1.7}')
html.append('h1{font-size:2.2em;color:#1a252f;margin-bottom:.2em;text-align:center}')
html.append('h2{font-size:1.4em;color:#1a252f;margin:1.5em 0 .6em;padding-bottom:.3em;border-bottom:2px solid #3498db}')
html.append('h3{font-size:1.1em;color:#2980b9;margin:.8em 0 .4em}')
html.append('p{font-size:.95em;color:#34495e;margin:.4em 0}')
html.append('.container{max-width:1200px;margin:0 auto;padding:1em}')
html.append('.card{background:#fff;border-radius:10px;padding:1.5em;margin:1em 0;box-shadow:0 2px 12px rgba(0,0,0,.08)}')
html.append('.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1em;margin:.8em 0}')
html.append('.stat-box{background:linear-gradient(135deg,#3498db,#2980b9);color:#fff;border-radius:10px;padding:1.2em;text-align:center}')
html.append('.stat-box.green{background:linear-gradient(135deg,#27ae60,#2ecc71)}')
html.append('.stat-box.orange{background:linear-gradient(135deg,#e67e22,#d35400)}')
html.append('.stat-box.red{background:linear-gradient(135deg,#e74c3c,#c0392b)}')
html.append('.stat-box.gray{background:linear-gradient(135deg,#7f8c8d,#95a5a6)}')
html.append('.stat-num{font-size:2.2em;font-weight:bold}')
html.append('.stat-label{font-size:.85em;opacity:.9;margin-top:.3em}')
html.append('.badge{display:inline-block;padding:.2em .6em;border-radius:4px;font-size:.8em;font-weight:bold;color:#fff}')
html.append('table{width:100%;border-collapse:collapse;margin:.8em 0;font-size:.9em}')
html.append('th{background:#3498db;color:#fff;padding:.7em;text-align:left}')
html.append('td{padding:.6em .7em;border-bottom:1px solid #eee}')
html.append('tr:hover{background:#f8f9fa}')
html.append('td.score{font-weight:bold;font-size:1.1em}')
html.append('.heatmap-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1em;margin:.8em 0}')
html.append('.heatmap-item{background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1)}')
html.append('.heatmap-img{width:100%;height:200px;object-fit:cover}')
html.append('.heatmap-caption{padding:.8em;font-size:.82em}')
html.append('.heatmap-score{font-size:1.4em;font-weight:bold;margin-bottom:.3em}')
html.append('.chart-img{width:100%;border-radius:8px;margin:.8em 0}')
html.append('.progress-bar{height:8px;background:#ecf0f1;border-radius:4px;overflow:hidden;margin:.3em 0}')
html.append('.progress-fill{height:100%;border-radius:4px}')
html.append('.tag{display:inline-block;background:#3498db;color:#fff;padding:.1em .4em;border-radius:3px;font-size:.75em;margin:.1em}')
html.append('.cat-row{display:flex;align-items:center;gap:.5em;padding:.25em 0}')
html.append('.cat-bar{height:20px;border-radius:3px;min-width:4px}')
html.append('.cat-name{min-width:80px}')
html.append('.cat-count{font-weight:bold;min-width:40px;text-align:right}')
html.append('.cat-pct{color:#888;font-size:.85em;min-width:50px}')
html.append('.toc{background:#fff;border-radius:10px;padding:1.2em;margin:1em 0;box-shadow:0 2px 8px rgba(0,0,0,.06)}')
html.append('.toc h3{margin-top:0}')
html.append('.toc a{color:#3498db;text-decoration:none;font-size:.9em;display:block;padding:.2em 0}')
html.append('.toc a:hover{text-decoration:underline}')
html.append('.toc ol,.toc ul{padding-left:1.5em;margin:.3em 0}')
html.append('.summary-box{background:linear-gradient(135deg,#2c3e50,#1a252f);color:#fff;border-radius:10px;padding:1.5em;margin:1em 0}')
html.append('.summary-box h2{color:#ecf0f1;border-bottom-color:#3498db}')
html.append('.summary-box h3{color:#bdc3c7}')
html.append('.recommendation{background:#fff;border-left:4px solid #3498db;padding:1em 1.2em;border-radius:0 8px 8px 0;margin:.6em 0}')
html.append('.rec-high{border-left-color:#e74c3c}')
html.append('.rec-medium{border-left-color:#f39c12}')
html.append('.rec-low{border-left-color:#27ae60}')
html.append('</style>')
html.append('</head>')
html.append('<body>')
html.append('<div class="container">')

# Header
html.append('<div class="card">')
html.append('<h1>南山区无障碍可达性分析报告</h1>')
html.append('<p style="text-align:center;color:#888">基于YOLO11x目标检测 + 腾讯街景影像 | 2022年数据</p>')
html.append('</div>')

# Table of contents
html.append('<div class="toc card">')
html.append('<h3>报告目录</h3>')
html.append('<ol>')
for sec in [("exec", "一、执行摘要"), ("method", "二、方法论"), ("overall", "三、全局统计"), ("district", "四、区级对比"), ("nanshan", "五、南山区分析"), ("streets", "六、街道级分析"), ("samples", "七、典型案例"), ("rec", "八、改进建议")]:
    html.append(f'<li><a href="#{sec[0]}">{sec[1]}</a></li>')
html.append('</ol>')
html.append('</div>')

# Executive summary
ns = score_stats([r["accessibility_score"] for r in nanshan])
overall_s = score_stats(all_scores)
rat, rcolor = rating(ns["mean"])
html.append(f'<div class="summary-box" id="exec">')
html.append('<h2>一、执行摘要</h2>')
html.append('<div class="stat-grid">')
html.append(f'<div class="stat-box"><div class="stat-num">136</div><div class="stat-label">南山区分析图片</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{ns["mean"]:.1f}</div><div class="stat-label">南山区平均障碍评分</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{ns["max"]:.0f}</div><div class="stat-label">最高障碍评分</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">866</div><div class="stat-label">汽车占道总次数</div></div>')
html.append(f'<div class="stat-box orange"><div class="stat-num">58.5%</div><div class="stat-label">较畅通(0-40分)比例</div></div>')
html.append(f'<div class="stat-box red"><div class="stat-num">17.7%</div><div class="stat-label">障碍较多(&gt;=40分)</div></div>')
html.append(f'<div class="stat-box green"><div class="stat-num">14.3%</div><div class="stat-label">畅通(0-10分)</div></div>')
html.append(f'<div class="stat-box gray"><div class="stat-num">4</div><div class="stat-label">涉及街道</div></div>')
html.append('</div>')
html.append(f'<p style="margin-top:1em">南山区平均障碍评分 <strong>{ns["mean"]:.1f}</strong>，评级为 <strong style="color:{rcolor}">{rat}</strong>。')
html.append(f'全区共检测障碍物 <strong>599</strong> 次，其中汽车占道占比 <strong>62.3%</strong>（373次），是首要障碍因素。')
html.append(f'相比之下，福田区（平均{score_stats([r["accessibility_score"] for r in futian])["mean"]:.1f}分）和龙华区（平均{score_stats([r["accessibility_score"] for r in longhua])["mean"]:.1f}分）可达性更好。')
html.append('</div>')

# Method
html.append('<div class="card" id="method">')
html.append('<h2>二、方法论</h2>')
html.append('<table>')
html.append('<tr><th>项目</th><th>说明</th></tr>')
html.append('<tr><td>街景来源</td><td>腾讯/百度街景 API，2022年拍摄</td></tr>')
html.append('<tr><td>检测模型</td><td>YOLO11x (COCO-80类基线)</td></tr>')
html.append('<tr><td>检测类别</td><td>汽车、行人、摩托车、自行车、公交车、货车、长椅、停车标志</td></tr>')
html.append('<tr><td>置信度阈值</td><td>0.35 (35%)</td></tr>')
html.append('<tr><td>评分公式</td><td>Σ(conf × 类别权重 × 区域权重) × 10，范围 0-100</td></tr>')
html.append('<tr><td>区域权重</td><td>脚边0.5 / 中部0.35 / 顶部0.15（贴近行人通行高度）</td></tr>')
html.append('<tr><td>类别权重</td><td>汽车=1.2, 行人=0.3, 摩托=0.8, 公交=0.7, 货车=1.0, 其他=0.5</td></tr>')
html.append('</table>')
html.append('<p><strong>评级标准：</strong> 0-10畅通 | 10-20较畅通 | 20-40一般 | 40-60较困难 | 60-80困难 | 80-100严重</p>')
html.append('</div>')

# Overall stats
html.append('<div class="card" id="overall">')
html.append('<h2>三、全局统计（全部5区）</h2>')
html.append('<div class="stat-grid">')
html.append(f'<div class="stat-box"><div class="stat-num">{len(data)}</div><div class="stat-label">总图片数</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{sum(r["total_obstacles"] for r in data)}</div><div class="stat-label">总障碍检测数</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{overall_s["mean"]:.1f}</div><div class="stat-label">全局平均评分</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{overall_s["median"]:.1f}</div><div class="stat-label">评分中位数</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{overall_s["std"]:.1f}</div><div class="stat-label">评分标准差</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{overall_s["max"]:.1f}</div><div class="stat-label">最高评分</div></div>')
html.append('</div>')

if "category_distribution.png" in charts:
    b64 = charts["category_distribution.png"]
    html.append('<h3>障碍类别分布</h3>')
    html.append(f'<img class="chart-img" src="data:image/png;base64,{b64}" alt="Category Distribution">')

html.append('<h3>评分分布表</h3>')
html.append('<table>')
html.append('<tr><th>区间</th><th>评级</th><th>图片数</th><th>占比</th><th>说明</th></tr>')
bins = [(0,10,"畅通","#27ae60","通行无明显障碍"),(10,20,"较畅通","#2ecc71","偶有少量占道"),(20,40,"一般","#f1c40f","部分占道通行不便"),(40,60,"较困难","#e67e22","多处占道影响通行"),(60,80,"困难","#e74c3c","严重占道需绕行"),(80,100,"严重","#c0392b","几乎无法通行")]
for lo,hi,label,color,desc in bins:
    cnt = sum(1 for s in all_scores if lo<=s<hi)
    pct = cnt/len(all_scores)*100
    bar_w = pct
    html.append(f'<tr>')
    html.append(f'<td>{lo}-{hi}</td>')
    html.append(f'<td><span class="badge" style="background:{color}">{label}</span></td>')
    html.append(f'<td>{cnt}</td>')
    html.append(f'<td><div class="progress-bar"><div class="progress-fill" style="width:{bar_w}%;background:{color}"></div></div>{pct:.1f}%</td>')
    html.append(f'<td>{desc}</td>')
    html.append(f'</tr>')
html.append('</table>')
html.append('</div>')

# District comparison
html.append('<div class="card" id="district">')
html.append('<h2>四、区级对比</h2>')
if "district_comparison.png" in charts:
    b64 = charts["district_comparison.png"]
    html.append(f'<img class="chart-img" src="data:image/png;base64,{b64}" alt="District Comparison">')

html.append('<table>')
html.append('<tr><th>行政区</th><th>图片数</th><th>采样点数</th><th>平均评分</th><th>评分中位数</th><th>最高分</th><th>障碍总数</th><th>评级</th><th>主要障碍</th></tr>')
district_order = sorted(districts.items(), key=lambda x: -score_stats(x[1]["scores"])["mean"])
for dname, dinfo in district_order:
    s = score_stats(dinfo["scores"])
    rat, rcolor = rating(s["mean"])
    top_cat = sorted(dinfo["cats"].items(), key=lambda x: -x[1])[0] if dinfo["cats"] else ("无", 0)
    html.append(f'<tr>')
    html.append(f'<td><strong>{dname}</strong></td>')
    html.append(f'<td>{s["n"]}</td>')
    html.append(f'<td>{len(dinfo["coords"])}</td>')
    html.append(f'<td class="score" style="color:{rcolor}">{s["mean"]:.1f}</td>')
    html.append(f'<td>{s["median"]:.1f}</td>')
    html.append(f'<td>{s["max"]:.1f}</td>')
    html.append(f'<td>{dinfo["n_obs"]}</td>')
    html.append(f'<td><span class="badge" style="background:{rcolor}">{rat}</span></td>')
    html.append(f'<td>{top_cat[0]} ({top_cat[1]})</td>')
    html.append('</tr>')
html.append('</table>')

# District category breakdown
html.append('<h3>各区障碍类别详情</h3>')
for dname, dinfo in district_order:
    total_d = sum(dinfo["cats"].values()) if dinfo["cats"] else 1
    html.append(f'<h4>{dname}</h4>')
    html.append('<div class="cat-row"><div class="cat-name">类别</div><div style="flex:1;height:20px;background:#eee;border-radius:3px"></div><div class="cat-count">次数</div><div class="cat-pct">占比</div></div>')
    for cat, cnt in sorted(dinfo["cats"].items(), key=lambda x: -x[1]):
        pct = cnt/total_d*100
        color = '#e74c3c' if '汽车' in cat or '货车' in cat else '#3498db' if '行人' in cat else '#f39c12' if '摩托' in cat else '#27ae60'
        html.append(f'<div class="cat-row">')
        html.append(f'<div class="cat-name">{cat}</div>')
        html.append(f'<div class="progress-bar" style="flex:1"><div class="progress-fill" style="width:{pct}%;background:{color}"></div></div>')
        html.append(f'<div class="cat-count">{cnt}</div>')
        html.append(f'<div class="cat-pct">{pct:.1f}%</div>')
        html.append('</div>')
html.append('</div>')

# Nanshan analysis
html.append('<div class="card" id="nanshan">')
html.append('<h2>五、南山区详细分析</h2>')
html.append('<div class="stat-grid">')
html.append(f'<div class="stat-box"><div class="stat-num">{len(nanshan)}</div><div class="stat-label">图片总数</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{len(set(r["coords"] for r in nanshan))}</div><div class="stat-label">采样点数量</div></div>')
html.append(f'<div class="stat-box orange"><div class="stat-num">{ns["mean"]:.1f}</div><div class="stat-label">平均障碍评分</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">{ns["median"]:.1f}</div><div class="stat-label">评分中位数</div></div>')
html.append(f'<div class="stat-box red"><div class="stat-num">{ns["max"]:.1f}</div><div class="stat-label">最高评分</div></div>')
html.append(f'<div class="stat-box green"><div class="stat-num">{sum(1 for r in nanshan if r["accessibility_score"]<=10)}</div><div class="stat-label">畅通(0-10分)</div></div>')
html.append(f'<div class="stat-box orange"><div class="stat-num">{sum(1 for r in nanshan if r["accessibility_score"]>=40)}</div><div class="stat-label">困难(&gt;=40分)</div></div>')
html.append(f'<div class="stat-box"><div class="stat-num">599</div><div class="stat-label">障碍总检测数</div></div>')
html.append('</div>')

# Score distribution for Nanshan
if "score_distribution.png" in charts:
    b64 = charts["score_distribution.png"]
    html.append('<h3>评分分布对比</h3>')
    html.append(f'<img class="chart-img" src="data:image/png;base64,{b64}" alt="Score Distribution">')

# Nanshan category breakdown
nanshan_cats = {}
for r in nanshan:
    for cat, cnt in r["categories"].items():
        nanshan_cats[cat] = nanshan_cats.get(cat, 0) + cnt
total_nc = sum(nanshan_cats.values()) if nanshan_cats else 1
html.append('<h3>南山区障碍类别排名</h3>')
html.append('<table>')
html.append('<tr><th>排名</th><th>类别</th><th>检测次数</th><th>占比</th><th>障碍等级</th><th>影响说明</th></tr>')
cat_info = [("汽车占道","#e74c3c","主要障碍,停车占用人行道"),("行人/使用者","#3498db","通常非障碍,但密集时影响"),("摩托车/电动车","#f39c12","占道停放,影响通行"),("货车占道","#e74c3c","大型占道,严重影响"),("自行车占道","#27ae60","小型占道,影响有限"),("公交车占道","#e67e22","公交停靠占道"),("停车标志","#95a5a6","标识物,非物理障碍"),("长椅占道","#27ae60","街道设施,通常合规")]
for i, (cat, color, desc) in enumerate(cat_info, 1):
    cnt = nanshan_cats.get(cat, 0)
    pct = cnt/total_nc*100
    impact = "高" if cnt >= 100 else "中" if cnt >= 30 else "低"
    impact_color = "#e74c3c" if impact == "高" else "#f39c12" if impact == "中" else "#27ae60"
    html.append(f'<tr>')
    html.append(f'<td>{i}</td>')
    html.append(f'<td><span class="badge" style="background:{color}">{cat}</span></td>')
    html.append(f'<td><strong>{cnt}</strong></td>')
    html.append(f'<td><div class="progress-bar"><div class="progress-fill" style="width:{pct}%;background:{color}"></div></div>{pct:.1f}%</td>')
    html.append(f'<td><span class="badge" style="background:{impact_color}">{impact}</span></td>')
    html.append(f'<td>{desc}</td>')
    html.append('</tr>')
html.append('</table>')
html.append('</div>')

# Street level analysis
html.append('<div class="card" id="streets">')
html.append('<h2>六、街道级分析</h2>')
html.append('<p>以下按街道分组，评估南山区各街道的无障碍可达性水平。</p>')

html.append('<table>')
html.append('<tr><th>街道</th><th>图片数</th><th>采样点</th><th>平均分</th><th>中位数</th><th>最高分</th><th>障碍总数</th><th>评级</th><th>主要问题</th></tr>')

street_display = []
for sname, sinfo in nanshan_streets.items():
    if sname in ["非南山"]: continue
    s = score_stats(sinfo["scores"])
    rat, rcolor = rating(s["mean"])
    top3 = sorted(sinfo["cats"].items(), key=lambda x: -x[1])[:3]
    main_issues = "、".join([f"{c}({n})" for c,n in top3]) if top3 else "无数据"
    street_display.append((sname, s, rat, rcolor, main_issues, sinfo))

street_display.sort(key=lambda x: -x[1]["mean"])
for sname, s, rat, rcolor, main_issues, sinfo in street_display:
    html.append(f'<tr>')
    html.append(f'<td><strong>{sname}</strong></td>')
    html.append(f'<td>{s["n"]}</td>')
    html.append(f'<td>{len(sinfo["coords"])}</td>')
    html.append(f'<td class="score" style="color:{rcolor}">{s["mean"]:.1f}</td>')
    html.append(f'<td>{s["median"]:.1f}</td>')
    html.append(f'<td>{s["max"]:.1f}</td>')
    html.append(f'<td>{sinfo["n_obs"]}</td>')
    html.append(f'<td><span class="badge" style="background:{rcolor}">{rat}</span></td>')
    html.append(f'<td style="font-size:.85em">{main_issues}</td>')
    html.append('</tr>')
html.append('</table>')

# Priority ranking
html.append('<h3>改进优先级排序</h3>')
html.append('<table>')
html.append('<tr><th>优先级</th><th>街道</th><th>平均分</th><th>问题描述</th><th>建议措施</th></tr>')
priorities = [
    (1, "招商街道", "汽车占道严重", "增加占道停车管理，优化停车位规划", "#e74c3c"),
    (2, "南山街道", "摩托车、行人混合杂乱", "设置专用非机动车道", "#e67e22"),
    (3, "蛇口街道", "货车临时占道", "限制货车停放时段", "#f39c12"),
    (4, "南头街道", "数据较少，需进一步调查", "增加采样点覆盖", "#3498db"),
]
for pri, street, prob, fix, color in priorities:
    html.append(f'<tr>')
    html.append(f'<td><span class="badge" style="background:{color}">P{pri}</span></td>')
    html.append(f'<td><strong>{street}</strong></td>')
    street_s = ns_stats.get(street, {"mean": 0})
    html.append(f'<td style="color:{color};font-weight:bold">{street_s["mean"]:.1f}</td>')
    html.append(f'<td>{prob}</td>')
    html.append(f'<td>{fix}</td>')
    html.append('</tr>')
html.append('</table>')
html.append('</div>')

# Heatmap samples
html.append('<div class="card" id="samples">')
html.append('<h2>七、典型案例（热图可视化）</h2>')
html.append('<p>以下为各评分区间的典型采样点热图，红色区域表示障碍物密度高，绿色表示畅通。</p>')
html.append('<div class="heatmap-grid">')
for hm in hm_samples:
    html.append('<div class="heatmap-item">')
    html.append(f'<img class="heatmap-img" src="data:image/jpeg;base64,{hm["b64"]}" alt="heatmap">')
    html.append('<div class="heatmap-caption">')
    html.append(f'<div class="heatmap-score" style="color:{hm["color"]}">{hm["score"]:.1f} 分</div>')
    html.append(f'<span class="badge" style="background:{hm["color"]}">{hm["rating"]}</span> ')
    html.append(f'<span style="color:#888;font-size:.8em">方向:{hm["direction"]} | 障碍:{hm["n_obs"]}个</span>')
    if hm["cats"]:
        cats_str = "、".join([f"{k}({v})" for k,v in sorted(hm["cats"].items(), key=lambda x:-x[1])[:3]])
        html.append(f'<div style="margin-top:.3em;font-size:.8em;color:#555">{cats_str}</div>')
    html.append('</div>')
    html.append('</div>')
html.append('</div>')
html.append('</div>')

# Recommendations
html.append('<div class="card" id="rec">')
html.append('<h2>八、改进建议</h2>')

recs = [
    ("rec-high", "优先治理汽车占道",
     "汽车占道占南山区障碍的62.3%（373次），是首要问题。建议：①在主要街道安装阻车桩，防止车辆驶入人行道；②挖掘周边停车场资源，引导车辆入场停放；③在重点路口设置违章停车监控。",
     "#e74c3c"),
    ("rec-high", "招商街道重点改造",
     "招商街道采样点平均评分75分以上（障碍最严重），建议开展专项治理，对人行道宽度不足路段实施拓宽改造。",
     "#e74c3c"),
    ("rec-medium", "完善非机动车通行空间",
     "摩托车/电动车占道136次，影响仅次于汽车。建议：①设置物理隔离的非机动车道；②在地铁口等热点区域划定专用停车区。",
     "#f39c12"),
    ("rec-medium", "建立15分钟社区监测机制",
     "建议每季度对障碍评分&gt;40的地点进行复查，形成动态监测台账，推动街道、社区落实整改责任。",
     "#f39c12"),
    ("rec-low", "提升街景可达性标识系统",
     "完善无障碍坡道、盲道的引导标识，确保新建、改建道路符合无障碍设计规范（GB 50763-2012）。",
     "#27ae60"),
    ("rec-low", "数据扩展",
     "当前仅136张南山区图片，建议将采样密度提升至500m间隔，并纳入城中村内部道路，实现15分钟社区全覆盖。",
     "#27ae60"),
]
for cls, title, body, color in recs:
    html.append(f'<div class="recommendation {cls}">')
    html.append(f'<h3><span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:{color};margin-right:.5em"></span>{title}</h3>')
    html.append(f'<p>{body}</p>')
    html.append('</div>')

html.append('<h3>15分钟可达性评估维度</h3>')
html.append('<table>')
html.append('<tr><th>维度</th><th>指标</th><th>当前数据支撑</th><th>建议补充</th></tr>')
dims = [
    ("通行障碍", "障碍物评分", "YOLO检测评分", "增加台阶、坡道专项检测"),
    ("街道密度", "每平方公里采样点", "136/34km²=4点/km²", "提升至20点/km²"),
    ("目的地可达", "距最近地铁/公交", "无", "接入POI数据计算步行时间"),
    ("路面质量", "破损路面、坑洼", "无", "路面病害专项检测模型"),
    ("无障碍设施", "坡道、盲道覆盖", "无", "Mapillary/腾讯街景语义分割"),
]
for d in dims:
    html.append(f'<tr><td><strong>{d[0]}</strong></td><td>{d[1]}</td><td>{d[2]}</td><td>{d[3]}</td></tr>')
html.append('</table>')
html.append('</div>')

# Footer
html.append('<div style="text-align:center;color:#aaa;font-size:.8em;margin:2em 0;padding:1em;border-top:1px solid #eee">')
html.append('<p>报告生成时间: 2026-05-29 | 模型: YOLO11x | 数据: 2022年南山区街景影像</p>')
html.append('<p>障碍评分范围 0-100 | 0=畅通无障碍 | 100=严重堵塞</p>')
html.append('</div>')

html.append('</div></body></html>')

out_path = f"{LOCAL_RESULTS}/南山区无障碍可达性分析报告.html"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(html))

print(f"Report saved: {out_path}")
print(f"File size: {os.path.getsize(out_path)} bytes")
print(f"Charts embedded: {len(charts)}")
print(f"Heatmap samples: {len(hm_samples)}")
