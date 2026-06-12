import json
from pathlib import Path

ckpt = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\checkpoint.json")
data = json.load(open(ckpt, encoding="utf-8"))

# Find parse_error cases and print full content
parse_errors = [x for x in data["done"] if x.get("status") == "parse_error"]
print(f"Parse errors: {len(parse_errors)}")
for x in parse_errors[:5]:
    print(f"\nFile: {x.get('path','?')}")
    print(f"Keys: {list(x.keys())}")
    raw = x.get("raw", "")
    err = x.get("error", "")
    print(f"raw len={len(raw)}, error len={len(err)}")
    print(f"raw repr[:300]: {repr(raw[:300])}")
    print(f"error[:300]: {err[:300]}")
