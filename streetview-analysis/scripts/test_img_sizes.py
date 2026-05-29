# -*- coding: utf-8 -*-
import base64, requests, csv, time
from pathlib import Path

API_KEY = "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"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Get first Nanshan image
BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
with open(BASE_DIR / "manifest.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
ns = [r for r in rows if r.get("district") == "南山区"]
p = Path(ns[0]["archive_path"])

with open(p, "rb") as f:
    raw = f.read()

print(f"Image: {p.name} | Size: {len(raw)} bytes", flush=True)

# Check JPEG magic bytes
print(f"Magic bytes: {raw[:4].hex()} (expect ffd8ffe0 or ffd8ffe1)", flush=True)
is_jpeg = raw[:2] == b'\xff\xd8'
print(f"Is valid JPEG: {is_jpeg}", flush=True)

# Test various sizes
PROMPT = 'Return JSON: {"building_pct": 50}'
tests = [
    ("full", raw, "data:image/jpeg;base64,{b64}"),
    ("half", raw[:len(raw)//2], "data:image/jpeg;base64,{b64}"),
    ("100KB", raw[:100000], "data:image/jpeg;base64,{b64}"),
    ("50KB", raw[:50000], "data:image/jpeg;base64,{b64}"),
]

for name, data, fmt in tests:
    b64 = base64.b64encode(data).decode("ascii")
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": PROMPT}
        ]}],
        "max_tokens": 64,
        "temperature": 0.1,
    }
    t = time.time()
    try:
        r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload, timeout=60)
        print(f"  {name} ({len(data)}b): {r.status_code} ({time.time()-t:.1f}s) | {r.text[:100]}", flush=True)
    except Exception as e:
        print(f"  {name}: ERROR {e}", flush=True)
    time.sleep(1)
