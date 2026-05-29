# -*- coding: utf-8 -*-
"""快速验证新prompt的差异性"""
import sys, base64, csv, json, re, time, requests
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

manifest = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\manifest.csv")
rows = []
with open(manifest, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        rows.append(row)

# 找3张不同城市形态的图像
seen_pts = set()
samples = []
for r in rows:
    if r.get("district", "").strip() == "南山区":
        pt = f"{r.get('lng')}_{r.get('lat')}"
        if pt not in seen_pts:
            seen_pts.add(pt)
            p = Path(r.get("archive_path", ""))
            if p.exists():
                samples.append((r, p))
                if len(samples) >= 3:
                    break

def parse(content):
    raw = content.strip()
    m = re.search(r'```json\s*(.*?)\s*```', raw, re.DOTALL)
    if m: raw = m.group(1).strip()
    else:
        s, e = raw.find('{'), raw.rfind('}')+1
        if s>=0 and e>s: raw = raw[s:e]
    km = {"建筑占比":"building_pct","道路占比":"road_pct","绿地占比":"green_pct","天空占比":"sky_pct"}
    for c,e in km.items(): raw = raw.replace(c,e)
    try: return json.loads(raw)
    except: return {"_raw": raw[:200]}

PROMPT = (
    "You are an urban geographer analyzing a street view image from Shenzhen, China.\n"
    "Look carefully at the image and estimate:\n"
    "- building_pct: percentage of image covered by buildings/structures (0-100)\n"
    "- road_pct: percentage covered by roads/pavement (0-100)\n"
    "- green_pct: percentage covered by trees/vegetation/grass (0-100)\n"
    "- sky_pct: percentage of sky visible (0-100)\n"
    "- openness: visual openness 1-10\n"
    "- street_canyon: street canyon effect 1-10\n"
    "- building_density: perceived building density 1-10\n"
    "- walkability: walkability 1-10\n"
    "- urban_form: (城中村/commodity_housing/old_community/new_community/industrial/commercial/public_space/other)\n"
    "- description_zh: brief Chinese description\n\n"
    "Output ONLY valid JSON:\n"
    "{\"building_pct\": 0, \"road_pct\": 0, \"green_pct\": 0, \"sky_pct\": 0, "
    "\"openness\": 0, \"street_canyon\": 0, \"building_density\": 0, "
    "\"walkability\": 0, \"urban_form\": \"\", \"description_zh\": \"\"}"
)

for i, (r, p) in enumerate(samples):
    with open(p, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    print(f"--- 图像{i+1} ---")
    print(f"  文件: {p.name}")
    print(f"  街道: {r.get('township')} | 归档城市形态: {r.get('urban_form')}")
    resp = requests.post(f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json={"model": "meta/llama-3.2-11b-vision-instruct",
              "messages": [{"role":"user","content":[
                  {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{img_b64}"}},
                  {"type":"text","text":PROMPT}
              ]}],
              "max_tokens": 256, "temperature": 0.2},
        timeout=90)
    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        data = parse(content)
        if "_raw" in data:
            print(f"  RAW: {content[:200]}")
        else:
            print(f"  建筑:{data.get('building_pct','?')}% "
                  f"道路:{data.get('road_pct','?')}% "
                  f"绿地:{data.get('green_pct','?')}% "
                  f"天空:{data.get('sky_pct','?')}%")
            print(f"  开阔度:{data.get('openness','?')} 峡谷:{data.get('street_canyon','?')} "
                  f"密度:{data.get('building_density','?')} 步行:{data.get('walkability','?')}")
            print(f"  形态:{data.get('urban_form','?')}")
            print(f"  描述:{data.get('description_zh','?')}")
    else:
        print(f"  错误: {resp.status_code}")
    print()
    time.sleep(1)
