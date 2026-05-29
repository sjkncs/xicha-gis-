# -*- coding: utf-8 -*-
"""快速测试 NVIDIA NIM API"""
import requests, json, base64, sys, time

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# 1. Test models endpoint
print("[1] 测试 /models ...")
try:
    resp = requests.get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"}, timeout=15)
    print(f"    状态: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        models = data.get('data', [])
        print(f"    可用模型数: {len(models)}")
        for m in models[:15]:
            print(f"    - {m.get('id', 'N/A')}")
    else:
        print(f"    错误: {resp.text[:300]}")
except Exception as e:
    print(f"    异常: {e}")

# 2. Test chat completions with a tiny image
print("\n[2] 测试 /chat/completions ...")
img_path = r"e:\xicha gis 智能定位\自选年份\baidu_streetview\南山区\粤海街道\未知\OpenOther-开放空间\113.938413_22.490341\113.938413_22.490341_N_2022.jpg"

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")
print(f"    图像大小: {len(img_b64)} bytes (base64)")

payload = {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": (
                    "分析这张街景图像，给出JSON格式的语义分割结果：\n"
                    "```json\n"
                    "{\n"
                    '  "building_pct": 0-100,\n'
                    '  "road_pct": 0-100,\n'
                    '  "green_pct": 0-100,\n'
                    '  "sky_pct": 0-100,\n'
                    '  "openness": 1-10,\n'
                    '  "street_canyon": 1-10,\n'
                    '  "building_density": 1-10,\n'
                    '  "walkability": 1-10,\n'
                    '  "urban_form": "城中村/商品房/老旧小区/新建小区/工业区/商业区/公共空间/其他",\n'
                    '  "description_zh": "一句话描述"\n'
                    "}\n"
                    "```"
                )}
            ]
        }
    ],
    "max_tokens": 512,
    "temperature": 0.1,
}

try:
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=120)
    t1 = time.time()
    print(f"    状态: {resp.status_code} | 耗时: {t1-t0:.1f}s")
    if resp.status_code == 200:
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        print(f"    Token使用: {usage}")
        # Extract JSON
        import re
        match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            print(f"\n    === 分析结果 ===")
            for k, v in data.items():
                print(f"    {k}: {v}")
        else:
            print(f"    原始回复: {content[:500]}")
    else:
        print(f"    错误: {resp.text[:500]}")
except Exception as e:
    print(f"    异常: {e}")
