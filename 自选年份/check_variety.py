# -*- coding: utf-8 -*-
"""检查模型是否真的在看图像 - 抽查不同图像的原始回复"""
import requests, base64, csv, json, re
from pathlib import Path

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

manifest = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\manifest.csv")
rows = []
with open(manifest, encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        rows.append(row)

# 找3张不同地点的图像
samples = []
for r in rows:
    if r.get("district", "").strip() == "南山区":
        p = Path(r.get("archive_path", ""))
        if p.exists():
            samples.append((r, p))
        if len(samples) >= 4:
            break

# 4张不同图：选4个不同采样点（每个点的第1张）
seen_pts = set()
unique_imgs = []
for r, p in samples:
    pt = f"{r.get('lng')}_{r.get('lat')}"
    if pt not in seen_pts:
        seen_pts.add(pt)
        unique_imgs.append((r, p))
    if len(unique_imgs) >= 4:
        break

print(f"抽查 {len(unique_imgs)} 张不同地点的图像\n")

PROMPT = (
    '分析这张深圳街景图像的建筑覆盖率、道路覆盖率、绿地覆盖率、天空占比，'
    '用JSON格式输出building_pct, road_pct, green_pct, sky_pct，'
    '数字必须根据实际图像内容估算，不要用模板值。'
)

for i, (r, p) in enumerate(unique_imgs):
    print(f"--- 图像 {i+1} ---")
    print(f"路径: {p.name}")
    print(f"街道: {r.get('township')} | 城市形态: {r.get('urban_form')}")
    print(f"坐标: {r.get('lng')}, {r.get('lat')}")

    with open(p, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 256,
        "temperature": 0.3,  # 稍微高一点看差异
    }

    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=90)
    if resp.status_code == 200:
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        # Parse JSON
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                print(f"建筑:{data.get('building_pct','?')}% 道路:{data.get('road_pct','?')}% "
                      f"绿地:{data.get('green_pct','?')}% 天空:{data.get('sky_pct','?')}%")
                print(f"原始: {content[:300]}")
            except:
                print(f"解析失败: {content[:300]}")
        else:
            print(f"无JSON: {content[:300]}")
    else:
        print(f"错误: {resp.status_code} {resp.text[:200]}")
    print()
