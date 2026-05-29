# -*- coding: utf-8 -*-
"""Quick test of NVIDIA NIM API with correct image path"""
import requests, json, base64, time, csv, re, sys
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Get first image from manifest
manifest = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\manifest.csv")
rows = []
with open(manifest, encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

# Find first NS image
ns_img = None
for r in rows:
    if r.get("district", "").strip() == "南山区":
        p = Path(r.get("archive_path", ""))
        if p.exists():
            ns_img = p
            break

if not ns_img:
    print("No NS image found!")
    sys.exit(1)

print(f"[测试图像] {ns_img}")
print(f"[文件大小] {ns_img.stat().st_size / 1024:.1f} KB")

# Read and encode
with open(ns_img, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode("utf-8")
print(f"[Base64长度] {len(img_b64)}")

# Call API
payload = {
    "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": (
                    "分析这张深圳街景图像，给出JSON格式的语义分割结果：\n"
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
                    "```\n"
                    "只输出JSON，不要其他文字。"
                )}
            ]
        }
    ],
    "max_tokens": 512,
    "temperature": 0.1,
}

print("\n正在调用 NVIDIA NIM API (nemotron-3-nano-omni-30b-a3b-reasoning)...")
t0 = time.time()
try:
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=120)
    t1 = time.time()
    print(f"响应状态: {resp.status_code} | 耗时: {t1-t0:.1f}s")

    if resp.status_code == 200:
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        print(f"\nToken使用: input={usage.get('prompt_tokens', '?')} "
              f"output={usage.get('completion_tokens', '?')} "
              f"total={usage.get('total_tokens', '?')}")

        # Extract JSON
        match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if not match:
            match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            print(f"\n=== 语义分割结果 ===")
            for k, v in data.items():
                print(f"  {k}: {v}")
        else:
            print(f"\n原始回复:\n{content[:800]}")
    else:
        print(f"错误: {resp.text[:500]}")
except Exception as e:
    print(f"异常: {e}")
