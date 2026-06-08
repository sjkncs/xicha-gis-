import json, csv
from pathlib import Path

BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
ckpt = BASE_DIR / "segmentation_results_v3" / "checkpoint.json"
data = json.load(open(ckpt, encoding="utf-8"))

# Find parse_error cases
parse_errors = [x for x in data["done"] if x.get("status") == "parse_error"]
print(f"Parse errors: {len(parse_errors)}")
print()
for x in parse_errors[:3]:
    print(f"File: {Path(x.get('path','')).name}")
    print(f"Township: {x.get('township','?')}")
    raw = x.get("raw", "")
    print(f"Raw (first 500): {repr(raw[:500])}")
    print(f"Raw (last 500): {repr(raw[-500:])}")
    print("-" * 60)
