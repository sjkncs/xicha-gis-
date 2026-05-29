import json, sys
sys.stdout.reconfigure(encoding='utf-8')

with open(r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_results_v2.json', 'r', encoding='utf-8') as f:
    raw = f.read()

data = json.loads(raw)
print("Top-level keys:", list(data.keys()) if isinstance(data, dict) else f"list of {len(data)} items")
if isinstance(data, dict):
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  '{k}': list of {len(v)} items")
            if v:
                print(f"    first item keys: {list(v[0].keys()) if isinstance(v[0], dict) else v[0]}")
                print(f"    first item: {json.dumps(v[0], ensure_ascii=False)[:300]}")
        else:
            print(f"  '{k}': {type(v).__name__} = {str(v)[:100]}")
