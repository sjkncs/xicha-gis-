import json
from pathlib import Path
ckpt = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\checkpoint.json")
if ckpt.exists():
    d = json.load(open(ckpt, encoding="utf-8"))
    done = d.get("done", [])
    ok = [x for x in done if x.get("status") in ("success", "partial")]
    err = [x for x in done if x.get("status") not in ("success", "partial")]
    print(f"progress: {len(done)}/136 | OK={len(ok)} | ERR={len(err)}")
    print(f"\nSample results (first 5):")
    for x in ok[:5]:
        fn = Path(x.get("path", "")).name
        print(f"  {fn}: bld={x.get('building_pct','?')} road={x.get('road_pct','?')} green={x.get('green_pct','?')} sky={x.get('sky_pct','?')} urban={x.get('urban_form','?')}")
    print(f"\nErrors ({len(err)}):")
    for x in err[:3]:
        fn = Path(x.get("path", "")).name
        print(f"  {fn}: {str(x.get('error',''))[:100]}")
else:
    print("no checkpoint")
