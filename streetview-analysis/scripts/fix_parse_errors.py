# -*- coding: utf-8 -*-
"""
从parse_error的描述文本中用正则提取建筑/道路/绿地/天空覆盖率
"""
import json, re, csv
from pathlib import Path
from collections import defaultdict
import statistics

CKPT = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\checkpoint.json")
OUT_CSV = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\seg_results_fixed.csv")

data = json.load(open(CKPT, encoding="utf-8"))
done = data["done"]

# ---- 文本覆盖率提取 ----
def extract_pct_from_text(text, field):
    """从描述文本中用正则提取百分比"""
    patterns = {
        "building_pct": [
            r"building[s]?[:\s]+(\d+)%", r"buildings[:\s]+(\d+)%",
            r"building coverage[:\s]+(\d+)%", r"building density[:\s]+(\d+)%",
            r"buildings represent[:\s]+(\d+)%", r"built-up[:\s]+(\d+)%",
            r"buildings? (?:occupy|cover|constitute|account for)[:\s]+(\d+)%",
            r"(\d+)% (?:of the |total )?(?:view|image|pixels)",
        ],
        "road_pct": [
            r"road[s]?[:\s]+(\d+)%", r"roadway[:\s]+(\d+)%",
            r"roads? (?:occupy|cover|constitute)[:\s]+(\d+)%",
        ],
        "green_pct": [
            r"vegetation[:\s]+(\d+)%", r"green[:\s]+(\d+)%",
            r"trees?[:\s]+(\d+)%", r"grass[:\s]+(\d+)%",
            r"greenery[:\s]+(\d+)%", r"open space[:\s]+(\d+)%",
        ],
        "sky_pct": [
            r"sky[:\s]+(\d+)%", r"open sky[:\s]+(\d+)%",
        ],
    }
    for pat in patterns.get(field, []):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return int(m.group(1))
    return None

def estimate_pct_from_desc(text):
    """用描述词估计覆盖率"""
    text_lower = text.lower()

    # 描述词 -> 估算值
    desc_map = {
        "building_pct": [
            ("high-rise dominating", 75), ("tall buildings dominating", 75),
            ("tall, medium, low-rise", 65), ("high-density", 65),
            ("dense residential", 60), ("dense development", 60),
            ("mixed tall and medium", 55), ("medium-rise dominating", 50),
            ("medium density", 45), ("moderate density", 40),
            ("commercial area", 50), ("residential area", 45),
            ("sprawling low-rise", 35), ("low-rise", 30),
            ("suburban", 25), ("sparse", 15), ("open", 10),
            ("industrial", 40), ("warehouses", 35),
        ],
        "road_pct": [
            ("wide multi-lane", 35), ("wide boulevard", 30), ("wide road", 30),
            ("multi-lane", 28), ("major road", 25), ("arterial", 25),
            ("secondary road", 20), ("narrow road", 15), ("lane", 15),
            ("alley", 10), ("pedestrian", 10), ("path", 8),
        ],
        "green_pct": [
            ("lush vegetation", 35), ("abundant trees", 30), ("dense trees", 25),
            ("green corridor", 20), ("tree-lined", 18), ("trees lining", 15),
            ("some trees", 12), ("sparse trees", 8), ("minimal vegetation", 5),
            ("nearly bare", 2), ("no vegetation", 1),
        ],
        "sky_pct": [
            ("vast open sky", 40), ("open sky", 30), ("limited sky", 10),
            ("very narrow", 5), ("canyon", 3), ("tight canyon", 2),
            ("boxed in", 2),
        ],
    }

    result = {}
    for field, keywords in desc_map.items():
        for kw, val in keywords:
            if kw in text_lower:
                result[field] = val
                break
    return result

def extract_openness_from_text(text):
    """从描述提取开阔度 1-10"""
    t = text.lower()
    if any(x in t for x in ["vast open", "open sky", "wide boulevard", "spacious"]): return 8
    if any(x in t for x in ["canyon", "boxed in", "tight", "narrow canyon", "very narrow"]): return 2
    if any(x in t for x in ["moderate", "balanced", "typical"]): return 5
    if any(x in t for x in ["some open", "limited", "constrained"]): return 4
    if any(x in t for x in ["high-density", "high rise", "tall buildings"]): return 3
    if any(x in t for x in ["low-rise", "suburban", "sparse"]): return 6
    return 5

def extract_canyon_from_text(text):
    """从描述提取峡谷感 1-10"""
    t = text.lower()
    if "tight canyon" in t or "severe canyon" in t: return 9
    if "canyon" in t: return 7
    if "high-rise on both" in t or "tall buildings on both" in t: return 7
    if "tall buildings" in t and "narrow" in t: return 6
    if "medium-rise" in t: return 5
    if "low-rise" in t or "suburban" in t: return 3
    if "wide road" in t or "boulevard" in t: return 3
    return 5

def extract_density(text):
    """从描述提取建筑密度 1-10"""
    t = text.lower()
    if "very high density" in t or "extremely dense" in t: return 9
    if "high density" in t or "high-density" in t: return 8
    if "dense" in t: return 7
    if "medium density" in t or "moderate density" in t: return 5
    if "low density" in t: return 3
    if "sparse" in t: return 2
    return 5

def extract_walkability(text):
    """从描述提取步行性 1-10"""
    t = text.lower()
    if "highly walkable" in t or "pedestrian-friendly" in t: return 8
    if "walkable" in t: return 7
    if "bicycle lane" in t or "bike lane" in t: return 7
    if "sidewalk" in t and "wide" in t: return 6
    if "sidewalk" in t: return 5
    if "narrow" in t and "pedestrian" in t: return 3
    if "no pedestrian" in t or "hostile" in t: return 2
    if "industrial" in t: return 3
    return 5

def extract_urban_form(text):
    """从描述推断城市形态"""
    t = text.lower()
    if "城中村" in text or "village" in t: return "城中村"
    if "commercial" in t and ("office" in t or "retail" in t or "mall" in t): return "commercial"
    if "industrial" in t or "warehouse" in t: return "industrial"
    if "residential" in t and "new" in t: return "new_community"
    if "old" in t and "residential" in t: return "old_community"
    if "commodity" in t or "high-end" in t: return "commodity_housing"
    if "public" in t or "park" in t: return "public_space"
    if "mixed-use" in t or "mixed use" in t: return "mixed_use"
    if "residential" in t: return "residential"
    return "other"

def estimate_1_10(text):
    d = extract_density(text)
    c = extract_canyon_from_text(text)
    o = extract_openness_from_text(text)
    w = extract_walkability(text)
    return {"openness": o, "canyon": c, "density": d, "walkability": w}

# ---- 修复parse_error ----
fixed_count = 0
for item in done:
    if item.get("status") != "parse_error":
        continue
    text = item.get("error", "")  # error字段里存的是描述文本
    if not text:
        continue

    # 先尝试直接数值提取
    pct = {}
    for field in ["building_pct", "road_pct", "green_pct", "sky_pct"]:
        pct[field] = extract_pct_from_text(text, field)

    # 如果没直接数值，用描述估计
    est = estimate_pct_from_desc(text)
    for k, v in est.items():
        if pct.get(k) is None:
            pct[k] = v

    # 如果还有缺失，用城区默认估计
    township = item.get("township", "")
    urban_form = item.get("urban_form", "")
    # 对未知urban_form的用描述推断
    if urban_form in ("未知", "", "open_other") or "?" in urban_form:
        item["urban_form"] = extract_urban_form(text)

    # 估计1-10指标
    metrics = estimate_1_10(text)
    for k, v in metrics.items():
        if item.get(k) is None:
            item[k] = v

    # 更新覆盖率
    for k, v in pct.items():
        if v is not None and item.get(k) is None:
            item[k] = v

    # 如果有足够数据，标记为partial
    has_pct = sum(1 for k in ["building_pct","road_pct","green_pct","sky_pct"] if item.get(k) is not None)
    if has_pct >= 3:
        item["status"] = "partial"
        # 补全缺失的百分比
        defaults = {"building_pct": 30, "road_pct": 15, "green_pct": 10, "sky_pct": 5}
        for k, v in defaults.items():
            if item.get(k) is None:
                item[k] = v
        fixed_count += 1
        print(f"  Fixed: {Path(item['path']).name} ({has_pct} pct fields) -> urban_form={item.get('urban_form','?')}")

print(f"\nFixed {fixed_count}/{len([x for x in done if x.get('status')=='parse_error'])} parse errors")

# ---- 保存修复后的CSV ----
all_fields = set()
for r in done:
    all_fields.update(r.keys())

priority = ["path", "filename", "heading", "township", "community",
            "urban_form", "road_name", "lng", "lat", "year", "point_key",
            "status", "building_pct", "road_pct", "green_pct", "sky_pct",
            "openness", "canyon", "density", "walkability",
            "description_zh", "tokens", "error", "raw"]
ordered = [f for f in priority if f in all_fields]
ordered += sorted(f for f in all_fields if f not in priority)

with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=ordered, extrasaction="ignore")
    w.writeheader()
    w.writerows(done)

print(f"Saved: {OUT_CSV} ({len(done)} rows)")

# ---- 统计汇总 ----
ok = [x for x in done if x.get("status") in ("success", "partial")]
err = [x for x in done if x.get("status") not in ("success", "partial")]

print(f"\nFinal: {len(done)} total | OK/partial={len(ok)} | ERR={len(err)}")

for field, label in [("building_pct","建筑"), ("road_pct","道路"), ("green_pct","绿地"), ("sky_pct","天空")]:
    vals = [x[field] for x in ok if x.get(field) is not None and x[field] not in ("?", None)]
    if vals:
        vals_f = [float(v) for v in vals]
        print(f"  {label}%: avg={statistics.mean(vals_f):.1f} range={min(vals_f):.0f}-{max(vals_f):.0f} median={statistics.median(vals_f):.1f}")

from collections import Counter
forms = Counter(x.get("urban_form","?") for x in ok)
print(f"\n城市形态分布:")
for k,v in forms.most_common():
    print(f"  {k}: {v}张({v/len(ok)*100:.1f}%)")

# 各街道统计
by_twp = defaultdict(list)
for x in ok:
    b = x.get("building_pct")
    if b is not None and b not in ("?", None):
        try: by_twp[x.get("township","?")].append(float(b))
        except: pass
print(f"\n各街道建筑覆盖率:")
for twp in sorted(by_twp, key=lambda t: statistics.mean(by_twp[t]), reverse=True):
    v = by_twp[twp]
    print(f"  {twp}: avg={statistics.mean(v):.1f}% n={len(v)}")
