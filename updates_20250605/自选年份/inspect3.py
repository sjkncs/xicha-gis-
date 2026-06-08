import json
from pathlib import Path

ckpt = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\checkpoint.json")
data = json.load(open(ckpt, encoding="utf-8"))
done = data["done"]

# 找parse_error
pe = [x for x in done if x.get("status") == "parse_error"]
print(f"parse_error count: {len(pe)}")
for x in pe[:3]:
    print(f"  path={x.get('path','?')[-60:]}")
    print(f"  status={x.get('status')}")
    print(f"  building_pct={x.get('building_pct')}")
    err = x.get("error","")
    print(f"  error[:200]={err[:200]}")
    print()

# 看其他错误类型
http_err = [x for x in done if x.get("status") == "http_error"]
print(f"http_error count: {len(http_err)}")
if http_err:
    print(f"  first: {http_err[0].get('error','')[:100]}")

# 看成功样例
ok = [x for x in done if x.get("status") in ("success","partial")]
print(f"\nsuccess/partial: {len(ok)}")
for x in ok[:2]:
    print(f"  status={x.get('status')}, building_pct={x.get('building_pct')}, urban_form={x.get('urban_form')}")
    print(f"  raw[:100]={repr(x.get('raw',''))[:100]}")
