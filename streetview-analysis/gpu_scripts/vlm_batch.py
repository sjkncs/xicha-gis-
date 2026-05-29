#!/usr/bin/env python3
"""处理高/中/低障碍物样例图的 VLM 标注"""
import os, json, re, base64, time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
OUT_DIR = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\vlm_output"
os.makedirs(OUT_DIR, exist_ok=True)

def get_font(size=18):
    for fp in ["C:/Windows/Fonts/msyh.ttc","C:/Windows/Fonts/simhei.ttc","C:/Windows/Fonts/simsun.ttc"]:
        if os.path.exists(fp):
            try: return ImageFont.truetype(fp, size)
            except: pass
    return ImageFont.load_default()

FC = {s: get_font(s) for s in [10, 11, 12, 14]}

def call_vlm(path, prompt):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    models = ["meta/llama-3.2-90b-vision-instruct", "microsoft/phi-3-vision-128k-instruct"]
    for model in models:
        t0 = time.time()
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [{"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt}
                ]}],
                "max_tokens": 512,
                "temperature": 0.1,
            },
            timeout=120,
        )
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"], model, time.time() - t0
    return None, None, None

PROMPT = (
    "You are an expert analyzing street view for pedestrian accessibility. "
    "Identify ALL obstacles: vehicles, street furniture, fences, walls, vegetation, pedestrians. "
    "For each obstacle: type, position (left/center/right/foreground), severity (high/medium/low), description. "
    "Estimate overall passability (0-100%). "
    "Output ONLY valid JSON (no markdown): "
    '{"obstacles":[{"type":"car","position":"center-right","severity":"high","description":"white sedan"}],"passability_estimate":45,"top_blocking":["car"]}'
)

SC = {"high": (220, 0, 0), "medium": (200, 120, 0), "low": (0, 160, 60)}
IC = {"high": "!", "medium": "~", "low": "o"}

def overlay(path, result, out):
    pil = Image.open(path).convert("RGB")
    a = np.array(pil)
    H, W = a.shape[:2]
    pi = pil.convert("RGBA")
    d = ImageDraw.Draw(pi)
    pw, ph = 300, min(300, H - 10)
    px, py = W - pw - 5, 5
    panel = Image.new("RGBA", (pw, ph), (240, 248, 255, 230))
    pd = ImageDraw.Draw(panel)
    pab = result.get("passability_estimate")
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
        nonlocal y
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
        sev_c = SC.get(sev, (100, 100, 100))
        icon = IC.get(sev, "-")
        put(f"#{i+1} {o.get('type', '?')} [{icon}]", 12, sev_c)
        d2 = o.get("description", "")[:25]
        pos = o.get("position", "")
        if d2:
            put(f"   {pos} | {d2}", 10, (80, 80, 80))
        y += 2

    top_blocking = result.get("top_blocking", [])
    if top_blocking:
        y += 3
        blocking_text = "主要阻断: " + ", ".join(str(t)[:15] for t in top_blocking[:3])
        put(blocking_text, 11, (180, 60, 20))

    pi.paste(panel, (px, py), mask=panel)
    pil_rgb = pi.convert("RGB")
    pil_rgb.save(out, quality=92)
    print(f"  [OK] Saved: {os.path.basename(out)} ({os.path.getsize(out)//1024}KB)")

def parse(content):
    try:
        c = re.sub(r"```json\s*", "", content)
        c = re.sub(r"```\s*", "", c)
        return json.loads(c)
    except:
        return {"obstacles": [], "passability_estimate": None, "top_blocking": []}

# 高/中/低障碍物样例
fig_dir = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures"
targets = [
    "fig_sim_high_obstacle.jpg",
    "fig_sim_moderate_obstacle.jpg",
    "fig_sim_low_obstacle.jpg",
    "fig_sim_sample1.png",
    "fig_sim_sample2.png",
]

for fname in targets:
    fp = os.path.join(fig_dir, fname)
    if not os.path.exists(fp):
        print(f"[SKIP] {fname} (not found)")
        continue
    print(f"\nProcessing: {fname}")
    content, model, elapsed = call_vlm(fp, PROMPT)
    if not content:
        print(f"  [FAIL] VLM error")
        continue
    result = parse(content)
    pab = result.get("passability_estimate")
    n = len(result.get("obstacles", []))
    print(f"  [OK] {model} ({elapsed:.1f}s) obs={n} pass={pab}%")
    for o in result.get("obstacles", [])[:3]:
        print(f"    - {o.get('type','?')} [{o.get('severity','?')}] {o.get('description','')[:40]}")
    ext = os.path.splitext(fname)[1]
    out = os.path.join(OUT_DIR, fname.replace(ext, "") + "_vlm.jpg")
    overlay(fp, result, out)

print(f"\nDone! Output: {OUT_DIR}")
