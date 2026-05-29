# -*- coding: utf-8 -*-
"""查看VLM原始输出，调试解析问题"""
import requests, json, base64, time, csv, re
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

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
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

PROMPT = (
    "你是一位城市地理专家，分析深圳街景图像。\n"
    "严格按以下JSON格式输出，不要有任何其他文字：\n"
    '{\n'
    '  "building_pct": 50,\n'
    '  "road_pct": 20,\n'
    '  "green_pct": 10,\n'
    '  "sky_pct": 20,\n'
    '  "openness": 6,\n'
    '  "street_canyon": 7,\n'
    '  "building_density": 8,\n'
    '  "walkability": 5,\n'
    '  "urban_form": "商品房住宅街区",\n'
    '  "description_zh": "描述"\n'
    '}\n'
)

def call_model(model_id, timeout=60):
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 256,
        "temperature": 0.1,
    }
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=timeout)
    t1 = time.time()
    if resp.status_code == 200:
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        return {"ok": True, "time": t1-t0, "content": content, "usage": result.get("usage", {})}
    else:
        return {"ok": False, "error": resp.text[:300]}

# Test 11B Llama Vision - fastest
print("测试 meta/llama-3.2-11b-vision-instruct...")
res = call_model("meta/llama-3.2-11b-vision-instruct")
if res["ok"]:
    print(f"耗时: {res['time']:.1f}s")
    print(f"Token: {res['usage']}")
    print(f"\n原始输出:")
    print(repr(res['content']))
    print(f"\n显示:")
    print(res['content'])
    # Try multiple parsing strategies
    print(f"\n--- 解析尝试 ---")
    # 1. 代码块json
    m = re.search(r'```json\s*(.*?)\s*```', res['content'], re.DOTALL)
    if m: print(f"1. 代码块json: OK -> {m.group(1)[:200]}")
    # 2. 裸 JSON
    m = re.search(r'\{[^{}]*"building_pct"[^{}]*\}', res['content'], re.DOTALL)
    if m: print(f"2. 裸JSON: OK -> {m.group(0)[:200]}")
    # 3. 首尾花括号
    start = res['content'].find('{')
    end = res['content'].rfind('}') + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(res['content'][start:end])
            print(f"3. 首尾花括号: OK -> {data}")
        except:
            print(f"3. 首尾花括号: FAIL")
    # 4. 替换中文key为英文
    content_clean = res['content']
    key_map = {
        "建筑占比": "building_pct", "道路占比": "road_pct", "绿地占比": "green_pct",
        "天空占比": "sky_pct", "开阔度": "openness", "街道峡谷效应": "street_canyon",
        "建筑密度": "building_density", "步行可达性": "walkability", "城市形态": "urban_form",
        "描述": "description_zh"
    }
    for cn, en in key_map.items():
        content_clean = content_clean.replace(cn, en)
    m = re.search(r'\{.*\}', content_clean, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            print(f"4. 中文key替换: OK -> {data}")
        except:
            print(f"4. 中文key替换: FAIL")
else:
    print(f"失败: {res.get('error')}")
