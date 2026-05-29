# -*- coding: utf-8 -*-
import requests, base64, csv, json, re, time
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}

manifest = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\manifest.csv")
rows = []
with open(manifest, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        rows.append(row)

ns_img = None
for r in rows:
    if r.get("district", "").strip() == "南山区":
        p = Path(r.get("archive_path", ""))
        if p.exists():
            ns_img = p
            break

with open(ns_img, "rb") as f:
    raw = f.read()
    img_b64 = base64.b64encode(raw).decode("utf-8")
print("Image size:", len(raw), "bytes")
print("Format:", raw[:4])
print("b64 length:", len(img_b64))

# Test different prompts
tests = [
    ("strict_json_english",
     'Analyze this street view image. Estimate: building coverage %(0-100), road %(0-100), green %(0-100), sky %(0-100). Return ONLY this JSON, nothing else: {"building":50,"road":20,"green":10,"sky":20}',
     0.01),
    ("strict_json_chinese",
     '你是一个城市地理专家。看图后请估计：建筑占比多少%(0-100)、道路占比多少%、绿地占比多少%、天空占比多少%。直接输出JSON：{"building":50,"road":20,"green":10,"sky":20}，只输出JSON，不要其他文字。',
     0.01),
    ("structured_continuation",
     'Analyze street view from Shenzhen. Estimate percentages. Return ONLY JSON:\n{"building":0,"road":0,"green":0,"sky":0}\nNo explanation.',
     0.01),
]

for test_name, prompt_text, temp in tests:
    print("\n--- " + test_name + " ---")
    payload = {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}},
            {"type": "text", "text": prompt_text}
        ]}],
        "max_tokens": 128,
        "temperature": temp,
    }
    t0 = time.time()
    resp = requests.post(BASE_URL + "/chat/completions", headers=HEADERS, json=payload, timeout=90)
    t1 = time.time()
    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        print("Time: %.1fs" % (t1-t0))
        print("Raw:", repr(content[:400]))
        # Try extract JSON
        m = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if m:
            try:
                print("Parsed:", json.loads(m.group(0)))
            except:
                print("JSON parse failed:", m.group(0)[:200])
    else:
        print("Error:", resp.status_code, resp.text[:200])
    time.sleep(1)
