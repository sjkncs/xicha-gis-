"""Quick VLM test on sample image"""
import os, json, re, base64, requests

API_KEY = "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"
img_path = r"e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures\fig_sim_sample1.png"

with open(img_path, "rb") as f:
    img_b64 = base64.b64encode(f.read()).decode()

prompt = (
    "You are an expert at analyzing urban street view images for pedestrian accessibility. "
    "Identify ALL obstacles that block pedestrian movement in this image. "
    "Look for: vehicles, street furniture, fences, construction barriers, dense vegetation, pedestrians, narrow passages. "
    "Output ONLY valid JSON (no markdown): "
    '{"obstacles":[{"type":"car","position":"center-right","severity":"high","description":"white sedan"}],"passability_estimate":45,"top_blocking":["car"]}'
)

payload = {
    "model": "meta/llama-3.2-90b-vision-instruct",
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                {"type": "text", "text": prompt}
            ]
        }
    ],
    "max_tokens": 512,
    "temperature": 0.1,
}

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
url = "https://integrate.api.nvidia.com/v1/chat/completions"

print("Calling llama-3.2-90b-vision-instruct...")
resp = requests.post(url, headers=headers, json=payload, timeout=120)
print("Status:", resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    print("Response preview:", content[:600])
else:
    print("Error:", resp.text[:400])
