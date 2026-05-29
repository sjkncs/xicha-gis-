# -*- coding: utf-8 -*-
import time, base64, requests, csv
from pathlib import Path

API_KEY = "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"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Read from manifest
BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
with open(BASE_DIR / "manifest.csv", encoding="utf-8") as f:
    ns_rows = [r for r in csv.DictReader(f) if r.get("district") == "南山区']

p = Path(ns_rows[0]["archive_path"])
print(f"Image: {p.name}", flush=True)
with open(p, "rb") as f:
    raw = f.read()
print(f"Size: {len(raw)} bytes", flush=True)

# Test 1: full image base64
b64 = base64.b64encode(raw).decode("ascii")
print(f"b64 length: {len(b64)} chars", flush=True)

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
print("Test 1: full image (base64)...", flush=True)
t = time.time()
try:
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test 2: tiny image
tiny_b64 = base64.b64encode(raw[:3000]).decode("ascii")
payload2 = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{tiny_b64}"}},
        {"type": "text", "text": PROMPT}
    ]}],
    "max_tokens": 128,
    "temperature": 0.1,
}
print("Test 2: tiny (3KB)...", flush=True)
t = time.time()
try:
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload2, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)

# Test 3: public URL
print("Test 3: public URL...", flush=True)
payload3 = {
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
    r = requests.post("https://integrate.api.nvidia.com/v1/chat/completions", headers=HEADERS, json=payload3, timeout=60)
    print(f"  {r.status_code} ({time.time()-t:.1f}s)", flush=True)
    print(f"  {r.text[:300]}", flush=True)
except Exception as e:
    print(f"  ERROR: {e}", flush=True)
