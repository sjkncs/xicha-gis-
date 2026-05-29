# -*- coding: utf-8 -*-
"""诊断：实际看看图像 + 调整prompt让模型输出JSON"""
import requests, base64, csv, json, re, time
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

print(f"测试图像: {ns_img}")
print(f"文件大小: {ns_img.stat().st_size} bytes")

# 检查图像
with open(ns_img, "rb") as f:
    data = f.read()
    img_b64 = base64.b64encode(data).decode("utf-8")
    print(f"Base64长度: {len(img_b64)}")
    print(f"前10字节: {data[:10]}")
    print(f"图像格式: {data[:4]}")

# 不同的prompt策略测试
prompts = [
    ("策略1-强制JSON(严格)", 
     '分析这张街景图像的建筑覆盖率(0-100)、道路覆盖率(0-100)、绿地覆盖率(0-100)、天空占比(0-100)。直接输出JSON：{"building":数字,"road":数字,"green":数字,"sky":数字}，只输出JSON。'),
    ("策略2-Chat格式+中文",
     '你是一个城市地理专家。看图后请估计：建筑占比是多少%（0-100）、道路占比多少%、绿地占比多少%、天空占比多少%。用JSON回答：{"building":50,"road":20,"green":10,"sky":20}，只输出JSON。'),
    ("策略3-强制结构化",
     'Return ONLY this exact JSON structure (fill in your estimates):\n'
     '{"building":0,"road":0,"green":0,"sky":0,"openness":0,"canyon":0,"density":0,"walk":0,"form":"type","note":""}\n'
     'Estimate each field from the image. Output ONLY the JSON, no explanation.'),
]

for name, prompt_text in prompts:
    print(f"\n{'='*60}")
    print("测试: " + name)
    print("-" * 60)
    
    payload = {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": prompt_text}
        ]}],
        "max_tokens": 128,
        "temperature": 0.01,  # 极低温度
    }
    
    t0 = time.time()
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=90)
    t1 = time.time()
    
    if resp.status_code == 200:
        content = resp.json()["choices"][0]["message"]["content"]
        print(f"耗时: {t1-t0:.1f}s")
        print(f"原始输出: {repr(content[:300])}")
        
        # 尝试解析
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
                print(f"解析结果: {parsed}")
            except:
                print(f"JSON解析失败: {m.group(0)[:200]}")
        else:
            print("无JSON结构")
    else:
        print(f"错误: {resp.status_code} {resp.text[:200]}")
    time.sleep(1)
