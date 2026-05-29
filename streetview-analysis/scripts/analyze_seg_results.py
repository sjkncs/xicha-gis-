# -*- coding: utf-8 -*-
import csv, json, statistics
from pathlib import Path
from collections import Counter, defaultdict

CSV = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\seg_results_final.csv")

rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
ok = [x for x in rows if x.get("status") in ("success", "partial")]
err = [x for x in rows if x.get("status") not in ("success", "partial")]

print(f"{'='*60}")
print(f"总记录: {len(rows)} | 有效: {len(ok)} | 失败: {len(err)}")
print(f"{'='*60}")

# 覆盖率统计
for field, label, unit in [
    ("building_pct","建筑覆盖率", "%"),
    ("road_pct",    "道路覆盖率", "%"),
    ("green_pct",   "绿地覆盖率", "%"),
    ("sky_pct",     "天空覆盖率", "%"),
]:
    vals = []
    for x in ok:
        v = x.get(field)
        if v and v not in ("?", None, ""):
            try:
                f = float(v)
                if f > 1: f = f / 100.0
                vals.append(f * 100)
            except:
                pass
    if vals:
        print(f"  {label}: avg={statistics.mean(vals):.1f}{unit} "
              f"median={statistics.median(vals):.1f}{unit} "
              f"range={min(vals):.0f}-{max(vals):.0f}{unit} n={len(vals)}")

print(f"\n城市形态分布:")
forms = Counter(x.get("urban_form","?") for x in ok)
for k,v in forms.most_common():
    print(f"  {k}: {v}张({v/len(ok)*100:.1f}%)")

print(f"\n各街道建筑覆盖率:")
by_twp = defaultdict(list)
for x in ok:
    v = x.get("building_pct")
    if v and v not in ("?", None, ""):
        try:
            f = float(v)
            if f > 1: f = f / 100.0
            by_twp[x.get("township","?")].append(f * 100)
        except:
            pass
for twp in sorted(by_twp, key=lambda t: statistics.mean(by_twp[t]), reverse=True):
    v = by_twp[twp]
    if len(v) >= 2:
        print(f"  {twp}: avg={statistics.mean(v):.1f}% n={len(v)}")

print(f"\n各街道绿地覆盖率:")
by_twp_g = defaultdict(list)
for x in ok:
    v = x.get("green_pct")
    if v and v not in ("?", None, ""):
        try:
            f = float(v)
            if f > 1: f = f / 100.0
            by_twp_g[x.get("township","?")].append(f * 100)
        except:
            pass
for twp in sorted(by_twp_g, key=lambda t: statistics.mean(by_twp_g[t]), reverse=True):
    v = by_twp_g[twp]
    if len(v) >= 2:
        print(f"  {twp}: avg={statistics.mean(v):.1f}% n={len(v)}")

print(f"\n各街道开放度(openness):")
by_twp_o = defaultdict(list)
for x in ok:
    v = x.get("openness")
    if v and v not in ("?", None, ""):
        try: by_twp_o[x.get("township","?")].append(float(v))
        except: pass
for twp in sorted(by_twp_o, key=lambda t: statistics.mean(by_twp_o[t]), reverse=True):
    v = by_twp_o[twp]
    if len(v) >= 2:
        print(f"  {twp}: avg={statistics.mean(v):.1f}/10 n={len(v)}")

print(f"\n失败记录 ({len(err)}):")
for x in err[:5]:
    print(f"  {Path(x.get('path','?')).name}: {x.get('status')} - {str(x.get('error',''))[:60]}")
