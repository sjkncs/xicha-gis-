# -*- coding: utf-8 -*-
"""找真正能分析图像内容的prompt策略"""
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

# 找3张差异最大的图像
samples = []
seen_pts = set()
for r in rows:
    if r.get("district", "").strip() == "南山区":
        pt = f"{r.get('lng')}_{r.get('lat')}"
        if pt not in seen_pts:
            seen_pts.add(pt)
            p = Path(r.get("archive_path", ""))
            if p.exists():
                samples.append((r, p))
                if len(samples) >= 5:
                    break

def encode(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def call(prompt_text, img_b64, temp=0.3, max_tok=256):
    payload = {
        "model": "meta/llama-3.2-11b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + img_b64}},
            {"type": "text", "text": prompt_text}
        ]}],
        "max_tokens": max_tok,
        "temperature": temp,
    }
    resp = requests.post(BASE_URL + "/chat/completions", headers=HEADERS, json=payload, timeout=90)
    if resp.status_code == 200:
        return resp.json()["choices"][0]["message"]["content"]
    return f"ERROR:{resp.status_code}"

def parse(content):
    # Try extract JSON from response
    m = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            pass
    return None

# 测试：同一张图，不同prompt
img0_b64 = encode(samples[0][1])
img1_b64 = encode(samples[1][1])
print("File0:", samples[0][1].name, samples[0][0].get("township"))
print("File1:", samples[1][1].name, samples[1][0].get("township"))
print()

# Strategy 1: Detailed analysis first, then structured extraction
p1 = (
    "You are an urban geographer. Describe in English what you see in this street view image "
    "from Shenzhen. Focus on: buildings (tall/medium/low, density), roads (wide/narrow), "
    "vegetation (trees, grass), sky visible. Give a brief factual description. "
    "Then at the end of your response, include a JSON object with your estimates: "
    '{"building_pct": number, "road_pct": number, "green_pct": number, "sky_pct": number, '
    '"openness": 1-10, "canyon": 1-10, "density": 1-10, "walkability": 1-10, '
    '"form": "城中村/商品房/etc", "note": "brief english note"}'
)

# Strategy 2: Ask about OBJECT COUNTS not percentages
p2 = (
    "Look at this street view image from Shenzhen. Count/estimate:\n"
    "1. Buildings: what percentage of the image is occupied by buildings? (0-100)\n"
    "2. Roads/pavement: what percentage? (0-100)\n"
    "3. Trees/vegetation: what percentage? (0-100)\n"
    "4. Sky: what percentage visible? (0-100)\n"
    "Answer in Chinese first, then give JSON: "
    '{"building":0,"road":0,"green":0,"sky":0}'
)

# Strategy 3: Step-by-step reasoning with "think"
p3 = (
    "<s>[INST] Analyze this image step by step. "
    "First, describe what types of buildings you see. "
    "Second, describe the road/street. "
    "Third, describe vegetation. "
    "Then provide your estimates. [/INST] "
    "<s>[INST] "
    "Based on my analysis: "
    "Building coverage (0-100): __\n"
    "Road coverage (0-100): __\n"
    "Green coverage (0-100): __\n"
    "Sky (0-100): __\n"
    "JSON: {\"building\":0,\"road\":0,\"green\":0,\"sky\":0} [/INST]"
)

# Strategy 4: No examples at all, just the question
p4 = (
    "Describe this Shenzhen street view image briefly in Chinese. "
    "Estimate: 建筑覆盖率(0-100%), 道路覆盖率(0-100%), 绿化率(0-100%), 天空比(0-100%)。 "
    "JSON输出: {\"b\":0,\"r\":0,\"g\":0,\"s\":0} 只输出JSON。"
)

strategies = [
    ("detailed_analysis_first", p1, 0.3),
    ("object_counts", p2, 0.3),
    ("chain_of_thought", p3, 0.1),
    ("chinese_no_examples", p4, 0.2),
]

for sname, sprompt, stemp in strategies:
    print("=" * 60)
    print("Strategy:", sname)
    print("-" * 60)
    
    # Two different images
    for i, (b64, sample) in enumerate([(img0_b64, samples[0]), (img1_b64, samples[1])]):
        content = call(sprompt, b64, temp=stemp)
        print("  Image%d %s [%s]:" % (i+1, sample[1].name, sample[0].get("township")))
        print("  Raw:", repr(content[:400]))
        parsed = parse(content)
        if parsed:
            print("  JSON:", parsed)
        else:
            # Try extract numbers
            nums = re.findall(r'"(building|b|pct)":\s*(\d+)', content, re.I)
            if nums:
                print("  Numbers found:", nums)
        print()
    time.sleep(1)
