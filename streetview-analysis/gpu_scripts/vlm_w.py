#!/usr/bin/env python3
"""快速处理 fig_sim_W_vlm.jpg"""
import os, json, re, base64, time, requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
OUT_DIR = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\vlm_output"
os.makedirs(OUT_DIR, exist_ok=True)

def get_font(size=18):
    for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttc"]:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

FC = {s: get_font(s) for s in [10, 11, 12, 14]}

PROMPT = (
    "You are an expert analyzing street view for pedestrian accessibility. "
    "Identify ALL obstacles: vehicles, street furniture, fences, walls, vegetation, pedestrians. "
    "Output ONLY valid JSON: "
    '{"obstacles":[{"type":"car","position":"center-right","severity":"high","description":"white sedan"}],"passability_estimate":45,"top_blocking":["car"]}'
)

SC = {"high": (220, 0, 0), "medium": (200, 120, 0), "low": (0, 160, 60)}
IC = {"high": "!", "medium": "~", "low": "o"}

fp = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures\fig_sim_W.jpg"
out = os.path.join(OUT_DIR, "fig_sim_W_vlm.jpg")

with open(fp, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
r = requests.post(
    f"{BASE_URL}/chat/completions",
    headers=headers,
    json={
        "model": "meta/llama-3.2-90b-vision-instruct",
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 512,
        "temperature": 0.1,
    },
    timeout=120,
)
content = r.json()["choices"][0]["message"]["content"]
result = json.loads(re.sub(r"```json\s*", "", re.sub(r"```\s*", "", content)))
pab = result.get("passability_estimate")
n = len(result.get("obstacles", []))
print(f"[OK] W view: obs={n} pass={pab}%")
for o in result.get("obstacles", [])[:3]:
    print(f"  - {o.get('type','?')} [{o.get('severity','?')}] {o.get('description','')[:40]}")

# overlay
pil = Image.open(fp).convert("RGB")
pi = pil.convert("RGBA")
H, W = np.array(pil).shape[:2]
pw, ph = 300, min(300, H - 10)
px, py = W - pw - 5, 5
panel = Image.new("RGBA", (pw, ph), (240, 248, 255, 230))
pd = ImageDraw.Draw(panel)
if pab is not None and pab >= 70:
    bc = (0, 160, 60)
elif pab is not None and pab >= 40:
    bc = (200, 140, 0)
elif pab is not None:
    bc = (200, 0, 0)
else:
    bc = (0, 150, 220)
pd.rectangle([0, 0, pw - 1, ph - 1], outline=(*bc, 255), width=2)
y = 8

def put(txt, fs=12, fc=(30, 30, 30)):
    global y
    fnt = FC.get(fs, get_font(fs))
    pd.text((8, y), txt, font=fnt, fill=(*fc, 255))
    y += fs + 7

put("[VLM] 障碍物识别", 14, (20, 80, 180))
put("-" * 28, 10, (150, 150, 150))
y += 3
if pab is not None:
    put(f"VLM通行率: {pab}%", 14, bc)
else:
    put("VLM通行率: N/A", 12, (100, 100, 100))
obs = result.get("obstacles", [])
put(f"识别障碍物: {len(obs)} 个", 12, (80, 60, 20))
put("-" * 28, 10, (150, 150, 150))
y += 3
for i, o in enumerate(obs[:7]):
    sev = o.get("severity", "")
    put(f"#{i+1} {o.get('type', '?')} [{IC.get(sev, '-')}]", 12, SC.get(sev, (100, 100, 100)))
    d2 = o.get("description", "")[:25]
    pos = o.get("position", "")
    if d2:
        put(f"   {pos} | {d2}", 10, (80, 80, 80))
    y += 2

pi.paste(panel, (px, py), mask=panel)
pi.convert("RGB").save(out, quality=92)
print(f"Saved: {out} ({os.path.getsize(out)//1024}KB)")

import shutil
dst = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures\fig_sim_W_vlm.jpg"
import shutil
shutil.copy(out, dst)
print(f"Copied to figures: {dst}")
