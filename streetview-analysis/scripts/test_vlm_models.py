# -*- coding: utf-8 -*-
"""测试 NVIDIA NIM 支持 vision 的模型"""
import requests, json, base64, time, csv, re
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# 读取一张测试图
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

if not ns_img:
    print("No image found!"); exit(1)

with open(ns_img, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")

print(f"测试图像: {ns_img.name}")
print(f"Base64长度: {len(img_b64)}")

PROMPT = (
    "你是一位城市地理专家，分析深圳街景图像。\n"
    "输出JSON格式的语义分割分析：\n"
    "建筑占比(0-100)、道路占比(0-100)、绿地占比(0-100)、"
    "天空占比(0-100)、开阔度(1-10)、街道峡谷效应(1-10)、"
    "建筑密度(1-10)、步行可达性(1-10)、城市形态、简短中文描述。\n"
    "只输出JSON，不要其他文字。"
)

def call_model(model_id, timeout=180):
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": PROMPT}
                ]
            }
        ],
        "max_tokens": 512,
        "temperature": 0.1,
    }

    t0 = time.time()
    try:
        resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=timeout)
        t1 = time.time()
        if resp.status_code == 200:
            result = resp.json()
            content = result["choices"][0]["message"]["content"]
            usage = result.get("usage", {})
            elapsed = t1 - t0
            # Try parse JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return {
                    "ok": True, "model": model_id,
                    "time": elapsed,
                    "tokens": usage.get("completion_tokens", 0),
                    "data": data
                }
            else:
                return {"ok": False, "model": model_id, "time": elapsed, "raw": content[:200]}
        else:
            return {"ok": False, "model": model_id, "status": resp.status_code,
                    "error": resp.text[:200], "time": time.time()-t0}
    except Exception as e:
        return {"ok": False, "model": model_id, "error": str(e)}

# 测试多个 VLM 模型
VLM_MODELS = [
    ("meta/llama-3.2-11b-vision-instruct", 60),   # 小型Llama视觉
    ("meta/llama-3.2-90b-vision-instruct", 120), # 大型Llama视觉
    ("microsoft/phi-3-vision-128k-instruct", 60),  # Phi视觉
    ("nvidia/llama-3.1-nemotron-nano-vl-8b-v1", 60),  # NVIDIA VL
    ("nvidia/nemotron-nano-12b-v2-vl", 60),       # NVIDIA Nano VL
]

for model_id, timeout in VLM_MODELS:
    print(f"\n{'='*60}")
    print(f"测试模型: {model_id} (timeout={timeout}s)")
    print('-'*60)
    res = call_model(model_id, timeout)
    if res["ok"]:
        d = res["data"]
        print(f"  状态: OK | 耗时: {res['time']:.1f}s | Tokens: {res['tokens']}")
        print(f"  建筑: {d.get('building_pct','?')}% | 道路: {d.get('road_pct','?')}% | 绿地: {d.get('green_pct','?')}%")
        print(f"  开阔度: {d.get('开阔度', d.get('openness','?'))} | 城市形态: {d.get('城市形态', d.get('urban_form','?'))}")
        print(f"  描述: {d.get('描述', d.get('description_zh','?'))}")
    else:
        print(f"  状态: FAIL | {res.get('error', res.get('raw', res.get('status','?')))}")
    # 每个模型之间稍作停顿
    time.sleep(2)
