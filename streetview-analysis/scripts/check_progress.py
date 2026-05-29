import json, csv
from pathlib import Path

ckpt = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\checkpoint.json")
csv_out = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\seg_results.csv")

if ckpt.exists():
    data = json.load(open(ckpt, encoding="utf-8"))
    items = data["done"]
    ok = [x for x in items if x.get("status") in ("success", "partial")]
    err = [x for x in items if x.get("status") not in ("success", "partial")]
    print(f"Checkpoint: total={data['count']} | ok={len(ok)} | err={len(err)}")

    # 统计
    bld = [x["building_pct"] for x in ok if "building_pct" in x and x["building_pct"] is not None]
    rd  = [x["road_pct"]    for x in ok if "road_pct"    in x and x["road_pct"]    is not None]
    grn = [x["green_pct"]   for x in ok if "green_pct"   in x and x["green_pct"]   is not None]
    sky = [x["sky_pct"]     for x in ok if "sky_pct"     in x and x["sky_pct"]     is not None]

    def avg(l): return sum(l)/len(l) if l else 0
    def rng(l): return f"{min(l)}-{max(l)}" if l else "N/A"
    def med(l): import statistics; return statistics.median(l) if l else 0

    if bld:
        print(f"\n覆盖率统计 (n={len(ok)}):")
        print(f"  建筑: avg={avg(bld):.1f}% range={rng(bld)} median={med(bld):.1f}%")
        print(f"  道路: avg={avg(rd):.1f}% range={rng(rd)}")
        print(f"  绿地: avg={avg(grn):.1f}% range={rng(grn)}")
        print(f"  天空: avg={avg(sky):.1f}% range={rng(sky)}")

    # 城市形态分布
    from collections import Counter
    forms = Counter(x.get("urban_form","?") for x in ok)
    print(f"\n城市形态分布:")
    for k,v in forms.most_common(10):
        print(f"  {k}: {v}张({v/len(ok)*100:.1f}%)")

    # 各街道
    from collections import defaultdict
    by_twp = defaultdict(list)
    for x in ok:
        b = x.get("building_pct")
        if b is not None: by_twp[x.get("township","?")].append(b)
    print(f"\n各街道建筑覆盖率:")
    for twp in sorted(by_twp):
        v = by_twp[twp]
        print(f"  {twp}: avg={avg(v):.1f}% n={len(v)}")

    # 错误详情
    if err:
        print(f"\n失败记录 ({len(err)}):")
        for x in err[:5]:
            print(f"  {x.get('filename','?')}: {x.get('status')} - {str(x.get('error',''))[:80]}")
else:
    print("checkpoint not found")
