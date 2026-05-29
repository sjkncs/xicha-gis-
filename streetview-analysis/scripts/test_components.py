# -*- coding: utf-8 -*-
import time, sys, json, base64, csv, re, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

t0 = time.time()
print("1. imports OK", flush=True)

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_ID = "meta/llama-3.2-11b-vision-instruct"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
BASE_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")
MANIFEST_PATH = BASE_DIR / "manifest.csv"

print("2. loading manifest...", flush=True)
t1 = time.time()
with open(MANIFEST_PATH, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
ns_rows = [r for r in rows if r.get("district") == "南山区"]
print(f"   {len(rows)} total, {len(ns_rows)} nanshan ({time.time()-t1:.1f}s)", flush=True)

p = Path(ns_rows[0].get("archive_path", ""))
print(f"3. image: {p.name} exists={p.exists()}", flush=True)

print("4. reading image...", flush=True)
with open(p, "rb") as f:
    data = f.read()
print(f"   read OK: {len(data)} bytes ({time.time()-t0:.1f}s)", flush=True)

print("5. base64 encode...", flush=True)
img_b64 = base64.b64encode(data).decode("ascii")
print(f"   b64 OK: {len(img_b64)} chars", flush=True)

print("6. API test (text-only first)...", flush=True)
test_payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": "Say exactly: TEST OK"}],
    "max_tokens": 32,
    "temperature": 0.1,
}
t2 = time.time()
try:
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=test_payload, timeout=60)
    print(f"   text-only: {resp.status_code} ({time.time()-t2:.1f}s)", flush=True)
    print(f"   content: {resp.text[:200]}", flush=True)
except Exception as e:
    print(f"   ERROR: {e}", flush=True)

print("7. API test (with small image)...", flush=True)
small_img = data[:20000]  # first 20KB
small_b64 = base64.b64encode(small_img).decode("ascii")
PROMPT = 'Say exactly: TEST OK in JSON like {"result": "OK"}.'
payload = {
    "model": MODEL_ID,
    "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{small_b64}"}},
        {"type": "text", "text": PROMPT}
    ]}],
    "max_tokens": 64,
    "temperature": 0.1,
}
t3 = time.time()
try:
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload, timeout=60)
    print(f"   with image: {resp.status_code} ({time.time()-t3:.1f}s)", flush=True)
    print(f"   content: {resp.text[:300]}", flush=True)
except Exception as e:
    print(f"   ERROR: {e}", flush=True)

print(f"\nDONE total={time.time()-t0:.1f}s", flush=True)
