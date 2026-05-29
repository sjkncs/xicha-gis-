# -*- coding: utf-8 -*-
"""
清理urban_form + 重试2个parse_error + 生成可视化报告
"""
import csv, json, re, base64, time, statistics, requests
from pathlib import Path
from collections import Counter, defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# 中文字体
for f in fm.fontManager.ttflist:
    if "SimHei" in f.name or "Heiti" in f.name or "Noto" in f.name or "CJK" in f.name or "Source Han" in f.name or "WenQuanYi" in f.name:
        plt.rcParams["font.family"] = f.name
        break
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3")
CSV_IN = BASE / "seg_results_final.csv"
CSV_OUT = BASE / "seg_final_clean.csv"
OUT_DIR = BASE / "viz_output"
OUT_DIR.mkdir(exist_ok=True)

# ==================== 1. 清理urban_form ====================
URBAN_MAP = {
    "城中村": "城中村",
    "commodity_housing": "商品房",
    "old_community": "老旧小区",
    "new_community": "新建住宅",
    "industrial": "工业",
    "commercial": "商业",
    "public_space": "公共空间",
    "residential": "居住",
    "mixed_use": "混合用途",
    "residential/commercial": "商住混合",
    "new_community/commodity_housing": "新建住宅",
    "commodity_housing/new_community": "新建住宅",
    "OpenOther-开放空间": "其他",
    "OpenOther": "其他",
    "Open/Other": "其他",
    "Low-Rise": "低层",
    "Mid-Rise": "中层",
    "Mixed": "混合",
    "open_other": "其他",
    "": "其他",
    "未知": "其他",
    "?": "其他",
}

def clean_urban_form(uf):
    if not uf: return "其他"
    uf = str(uf).strip()
    # 取第一个选项
    if "/" in uf:
        uf = uf.split("/")[0].strip()
    return URBAN_MAP.get(uf, URBAN_MAP.get(uf.lower(), "其他"))

# ==================== 2. 百分比转换 ====================
def to_pct(val):
    if not val or val in ("?", None, ""): return None
    try:
        f = float(val)
        if f > 1: f = f / 100.0
        return round(f, 4)
    except: return None

def to_pct_display(val):
    """转为显示用百分比字符串"""
    p = to_pct(val)
    if p is None: return "N/A"
    return f"{p*100:.0f}%"

# ==================== 3. 重试2个parse_error ====================
API_KEY = "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"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

PROMPT = (
    'You are an urban geographer analyzing Shenzhen street view. '
    'Give a brief description. '
    'Then return ONLY valid JSON with these exact keys: '
    '{"building_pct": 60, "road_pct": 20, "green_pct": 10, "sky_pct": 10, '
    '"openness": 5, "canyon": 5, "density": 7, "walkability": 6, '
    '"urban_form": "new_community", '
    '"description_zh": "城市形态描述"}'
)

def extract_json(content):
    start = content.rfind("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end+1])
        except:
            pass
    return None

def retry_image(item):
    p = item["path"]
    print(f"  Retrying: {Path(p).name}", flush=True)
    try:
        with open(p, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return None

    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 256,
        "temperature": 0.1,
    }
    try:
        r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions",
            headers=HEADERS, json=payload, timeout=90)
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"]
            parsed = extract_json(content)
            if parsed:
                for k, v in parsed.items():
                    if k in ("building_pct","road_pct","green_pct","sky_pct"):
                        item[k] = to_pct(v)
                    elif k in ("openness","canyon","density","walkability"):
                        item[k] = v
                    elif k == "urban_form":
                        item[k] = v
                item["status"] = "success"
                b = item.get("building_pct")
                print(f"    OK: bld={to_pct_display(b)} urban={item.get('urban_form','?')}")
                return item
        item["status"] = "still_failed"
    except Exception as e:
        item["status"] = "still_failed"
        item["error"] = str(e)
    return None

# ==================== 4. 加载并处理 ====================
print("Loading data...")
rows = list(csv.DictReader(open(CSV_IN, encoding="utf-8")))
print(f"Total: {len(rows)}")

# 清理urban_form
for r in rows:
    r["urban_form_clean"] = clean_urban_form(r.get("urban_form", ""))
    r["building_pct_f"] = to_pct(r.get("building_pct"))
    r["road_pct_f"] = to_pct(r.get("road_pct"))
    r["green_pct_f"] = to_pct(r.get("green_pct"))
    r["sky_pct_f"] = to_pct(r.get("sky_pct"))

# 重试2个失败
failed = [r for r in rows if r.get("status") not in ("success","partial")]
print(f"Failed: {len(failed)}")
if failed:
    print("Retrying failed images...")
    time.sleep(5)
    for r in failed:
        retry_image(r)

ok = [r for r in rows if r.get("status") in ("success","partial")]
print(f"\nTotal OK: {len(ok)}/{len(rows)}")

# ==================== 5. 统计汇总 ====================
print(f"\n{'='*60}")
print("城市形态分布 (清理后):")
forms_clean = Counter(r["urban_form_clean"] for r in ok)
for k, v in forms_clean.most_common():
    print(f"  {k}: {v}张({v/len(ok)*100:.1f}%)")

for field, label, unit in [
    ("building_pct_f","建筑覆盖率","%"),
    ("road_pct_f","道路覆盖率","%"),
    ("green_pct_f","绿地覆盖率","%"),
    ("sky_pct_f","天空覆盖率","%"),
]:
    vals = [r[field] for r in ok if r[field] is not None]
    if vals:
        display = [v*100 for v in vals]
        print(f"  {label}: avg={statistics.mean(display):.1f}{unit} median={statistics.median(display):.1f}{unit} range={min(display):.0f}-{max(display):.0f}{unit}")

print(f"\n各街道建筑覆盖率:")
by_twp = defaultdict(list)
for r in ok:
    b = r["building_pct_f"]
    if b is not None:
        by_twp[r.get("township","?")].append(b*100)
for twp in sorted(by_twp, key=lambda t: statistics.mean(by_twp[t]), reverse=True):
    v = by_twp[twp]
    if len(v) >= 2:
        print(f"  {twp}: avg={statistics.mean(v):.1f}% median={statistics.median(v):.1f}% n={len(v)}")

# ==================== 6. 保存清理后CSV ====================
# 重新排列字段顺序
priority = ["path","filename","heading","township","community","urban_form","urban_form_clean",
            "road_name","lng","lat","year","point_key","status",
            "building_pct","building_pct_f","road_pct","road_pct_f",
            "green_pct","green_pct_f","sky_pct","sky_pct_f",
            "openness","canyon","density","walkability",
            "description_zh","tokens","error","raw"]
all_keys = set()
for r in rows: all_keys.update(r.keys())
ordered = [f for f in priority if f in all_keys]
ordered += sorted(f for f in all_keys if f not in priority)

with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
print(f"\nSaved: {CSV_OUT}")

# ==================== 7. 可视化 ====================
print(f"\nGenerating visualizations...")

# 7a. 城市形态饼图
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
form_counts = Counter(r["urban_form_clean"] for r in ok)
labels = [f"{k} ({v})" for k,v in form_counts.most_common()]
sizes = [v for k,v in form_counts.most_common()]
colors = plt.cm.Set3(np.linspace(0,1,len(sizes)))
axes[0].pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=90)
axes[0].set_title("Urban Form Distribution\n城市形态分布", fontsize=12)

# 7b. 各街道覆盖率箱线图
twps = sorted(by_twp.keys(), key=lambda t: statistics.mean(by_twp[t]), reverse=True)
twps_data = [by_twp[t] for t in twps if len(by_twp[t]) >= 2]
twps_labels = [t for t in twps if len(by_twp[t]) >= 2]
if twps_data:
    bp = axes[1].boxplot(twps_data, labels=twps_labels, patch_artist=True, vert=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("lightblue")
    axes[1].set_ylabel("Building Coverage (%)", fontsize=10)
    axes[1].set_title("Building Coverage by Township\n各街道建筑覆盖率", fontsize=12)
    axes[1].tick_params(axis="x", rotation=30, labelsize=8)
    axes[1].grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(OUT_DIR / "urban_form_by_township.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {OUT_DIR / 'urban_form_by_township.png'}")

# 7c. 覆盖率分布直方图
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for ax, (field, label) in zip(axes.flat, [
    ("building_pct_f","Building Coverage / 建筑覆盖率"),
    ("road_pct_f","Road Coverage / 道路覆盖率"),
    ("green_pct_f","Green Coverage / 绿地覆盖率"),
    ("sky_pct_f","Sky Openness / 天空可见度"),
]):
    vals = [r[field]*100 for r in ok if r[field] is not None]
    if vals:
        ax.hist(vals, bins=20, color="steelblue", alpha=0.7, edgecolor="white")
        ax.axvline(statistics.mean(vals), color="red", linestyle="--", label=f"Mean={statistics.mean(vals):.1f}%")
        ax.axvline(statistics.median(vals), color="orange", linestyle="--", label=f"Median={statistics.median(vals):.1f}%")
        ax.set_xlabel("%")
        ax.set_ylabel("Count")
        ax.set_title(label, fontsize=10)
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(OUT_DIR / "coverage_histograms.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {OUT_DIR / 'coverage_histograms.png'}")

# 7d. 各街道建筑覆盖率热力条形图
fig, ax = plt.subplots(figsize=(12, 8))
twps_sorted = sorted(by_twp.keys(), key=lambda t: statistics.mean(by_twp[t]))
avgs = [statistics.mean(by_twp[t]) for t in twps_sorted]
ns = [len(by_twp[t]) for t in twps_sorted]
colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(avgs)))
bars = ax.barh(range(len(twps_sorted)), avgs, color=colors)
for i, (v, n) in enumerate(zip(avgs, ns)):
    ax.text(v + 0.5, i, f"{v:.1f}% (n={n})", va="center", fontsize=9)
ax.set_yticks(range(len(twps_sorted)))
ax.set_yticklabels(twps_sorted, fontsize=9)
ax.set_xlabel("Building Coverage (%)")
ax.set_title("Building Coverage by Township / 各街道建筑覆盖率", fontsize=12)
ax.set_xlim(0, max(avgs) + 15)
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "building_coverage_by_township.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {OUT_DIR / 'building_coverage_by_township.png'}")

# 7e. 散点图: 建筑 vs 绿地
fig, ax = plt.subplots(figsize=(10, 8))
colors_map = {
    "城中村": "red", "商品房": "blue", "新建住宅": "green",
    "老旧小区": "orange", "商业": "purple", "其他": "gray",
    "工业": "brown", "公共空间": "cyan", "居住": "pink",
    "混合用途": "yellow", "商住混合": "salmon",
}
for uf in set(r["urban_form_clean"] for r in ok):
    sub = [r for r in ok if r["urban_form_clean"] == uf and r["building_pct_f"] is not None and r["green_pct_f"] is not None]
    if sub:
        x = [r["building_pct_f"]*100 for r in sub]
        y = [r["green_pct_f"]*100 for r in sub]
        ax.scatter(x, y, alpha=0.6, label=f"{uf} (n={len(sub)})", c=colors_map.get(uf,"gray"), s=50)
ax.set_xlabel("Building Coverage (%)")
ax.set_ylabel("Green Coverage (%)")
ax.set_title("Building vs Green Coverage by Urban Form\n建筑覆盖率 vs 绿地覆盖率")
ax.legend(fontsize=8, loc="upper right")
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(OUT_DIR / "building_vs_green_scatter.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {OUT_DIR / 'building_vs_green_scatter.png'}")

# 7f. 雷达图: 各街道形态指标
metrics = ["openness","canyon","density","walkability"]
metric_labels = {"openness":"开放度","canyon":"峡谷感","density":"密度","walkability":"步行性"}
by_twp_metric = defaultdict(dict)
for r in ok:
    tw = r.get("township","?")
    for m in metrics:
        v = r.get(m)
        if v:
            try: by_twp_metric[tw][m] = by_twp_metric[tw].get(m, []) + [float(v)]
            except: pass

fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
top_twps = sorted(by_twp_metric.keys(), key=lambda t: len(by_twp_metric[t]), reverse=True)[:8]
angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
angles += angles[:1]
for tw in top_twps:
    vals = [statistics.mean(by_twp_metric[tw].get(m, [5])) for m in metrics]
    vals += vals[:1]
    ax.plot(angles, vals, 'o-', linewidth=2, label=tw, alpha=0.7)
    ax.fill(angles, vals, alpha=0.1)
ax.set_xticks(angles[:-1])
ax.set_xticklabels([metric_labels.get(m,m) for m in metrics], fontsize=10)
ax.set_ylim(0, 10)
ax.set_title("Township Urban Metrics Radar / 各街道城市指标雷达", fontsize=12, pad=20)
ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0), fontsize=8)
plt.tight_layout()
plt.savefig(OUT_DIR / "township_radar.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {OUT_DIR / 'township_radar.png'}")

# ==================== 8. 输出报告 ====================
print(f"\n{'='*60}")
print(f"完成! 可视化保存在: {OUT_DIR}")
print(f"清理后CSV: {CSV_OUT}")
print(f"有效记录: {len(ok)}/{len(rows)}")
