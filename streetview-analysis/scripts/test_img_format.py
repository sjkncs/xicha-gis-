# -*- coding: utf-8 -*-
import time, base64, requests
from pathlib import Path

API_KEY = "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"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

p = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview\南山区\粤海街道\未知\OpenOther-开放空间\113.938413_22.490341\113.938413_22.490341_N_2022.jpg")

print(f"Image: {p.name}", flush=True)
with open(p, "rb") as f:
    raw = f.read()
print(f"Size: {len(raw)} bytes", flush=True)

b64 = base64.b64encode(raw).decode("ascii")
print(f"b64 length: {len(b64)} chars", flush=True)

# Test 1: full image
PROMPT = 'Describe this image briefly, then output JSON: {"result": "ok", "building_pct": 50}'
payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        {"type": "text", "text": PROMPT}
    ]}],
    "max_tokens": 128,
    "temperature": 0.1,
}
print("Test 1: full image...", flush=True)
t = time.time()
try:
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:200]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test 2: tiny image
tiny = raw[:5000]
tiny_b64 = base64.b64encode(tiny).decode("ascii")
payload2 = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{tiny_b64}"}},
        {"type": "text", "text": PROMPT}
    ]}],
    "max_tokens": 128,
    "temperature": 0.1,
}
print("Test 2: tiny image (5KB)...", flush=True)
t = time.time()
try:
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload2, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:200]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test 3: url instead of base64
print("Test 3: public URL...", flush=True)
url_payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "https://placehold.co/600x400/jpeg"}},
        {"type": "text", "text": PROMPT}
    ]}],
    "max_tokens": 128,
    "temperature": 0.1,
}
t = time.time()
try:
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=url_payload, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)
