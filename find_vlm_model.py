# -*- coding: utf-8 -*-
"""List all NVIDIA models and test multimodal"""
import requests
import base64
import time

NVAPI_KEY = os.environ.get('NVIDIA_API_KEY', '').strip()
if not NVAPI_KEY:
    raise RuntimeError('Set NVIDIA_API_KEY before running this script.')
BASE_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'
HEADERS = {
    'Authorization': f'Bearer {NVAPI_KEY}',
    'Content-Type': 'application/json',
}

def get_models():
    resp = requests.get('https://integrate.api.nvidia.com/v1/models',
                       headers={'Authorization': f'Bearer {NVAPI_KEY}'}, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        models = data.get('data', [])
        return [m.get('id') for m in models if m.get('id')]
    return []

def chat(model, messages, max_tokens=128):
    payload = {'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': 0.1}
    resp = requests.post(BASE_URL, headers=HEADERS, json=payload, timeout=30)
    data = resp.json()
    if 'choices' in data and data['choices']:
        msg = data['choices'][0]['message']
        return msg.get('content') or msg.get('reasoning_content') or ''
    return f'ERROR: {str(data)[:200]}'

print('All available models:')
models = get_models()
for m in models:
    print(f'  {m}')

# Focus on multimodal/VLM models
print('\n=== Vision/Multimodal models ===')
vlm_keywords = ['vision', 'clip', 'llava', 'qwen', 'instruct', 'phi', 'minicpm', 'paligemma', 'gemma-3', 'fuyu', 'deplot']
vlm_models = [m for m in models if any(k in m.lower() for k in vlm_keywords)]
for m in vlm_models[:15]:
    print(f'  {m}')

# Test text completion
print('\n=== Text test ===')
text = chat('nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
             [{'role': 'user', 'content': 'What city is this location in: Shenzhen? Answer with just the city name.'}],
             max_tokens=64)
print(f'Text: {text[:200]}')

# Test image with deplot (known multimodal model)
print('\n=== Image test with deplot ===')
# Use a simple test image
import os
img_path = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\dl_pipeline\images\raw\amap_z16_w600_h400_140c6750.png'
if os.path.exists(img_path):
    with open(img_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    messages = [
        {'role': 'user', 'content': [
            {'type': 'text', 'text': 'Describe what you see in this image briefly.'},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64[:100000]}'}}
        ]}
    ]
    # Try deplot
    result = chat('google/deplot', messages, max_tokens=128)
    print(f'deplot: {result[:200]}')
    time.sleep(1)

# Try adept/fuyu
print('\n=== Image test with fuyu-8b ===')
if os.path.exists(img_path):
    with open(img_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode()
    messages = [
        {'role': 'user', 'content': [
            {'type': 'text', 'text': 'What is in this image? Short answer.'},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64[:100000]}'}}
        ]}
    ]
    result = chat('adept/fuyu-8b', messages, max_tokens=128)
    print(f'fuyu-8b: {result[:200]}')
    time.sleep(1)

# Try qwen-vl
qwen_models = [m for m in models if 'qwen' in m.lower() and ('vl' in m.lower() or 'vision' in m.lower())]
print(f'\nQwen VL models: {qwen_models}')
for m in qwen_models[:3]:
    if os.path.exists(img_path):
        with open(img_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()
        messages = [{'role': 'user', 'content': [
            {'type': 'text', 'text': 'Describe image briefly.'},
            {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64[:50000]}'}}
        ]}]
        result = chat(m, messages, max_tokens=64)
        print(f'{m}: {result[:200]}')
        time.sleep(1)
