# -*- coding: utf-8 -*-
"""列出NVIDIA NIM中支持vision的模型"""
import requests, json

API_KEY = "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"
BASE_URL = "https://integrate.api.nvidia.com/v1"

resp = requests.get(
    f"{BASE_URL}/models",
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30
)
data = resp.json()
models = data.get('data', [])
print(f"总模型数: {len(models)}")

# 找 vision/multimodal 模型
vision_models = []
all_ids = []
for m in models:
    mid = m.get('id', '')
    all_ids.append(mid)
    # 检查是否是vision模型
    if any(kw in mid.lower() for kw in ['vision', 'vl', 'llava', 'qwen-vl', 'qwen2-vl', 'qwen2.5-vl',
                                          'qwen-vl', 'cogvlm', 'minicpm-v', 'emu', 'internvl',
                                          'glm-v', 'baichuan-v', 'deepseek-vl', 'aimany',
                                          'pixtral', 'mistral-vl', 'llama-vl', ' Granite',
                                          'nemotron', 'omni', 'screen', 'visual', 'image']):
        vision_models.append(m)

print(f"\n=== 可能支持视觉/VLM的模型 ({len(vision_models)}) ===")
for m in vision_models:
    print(f"  - {m.get('id')}")

# 找 nvidia 品牌模型
nvidia_models = [m for m in models if m.get('id', '').startswith('nvidia/')]
print(f"\n=== NVIDIA 品牌模型 ({len(nvidia_models)}) ===")
for m in nvidia_models:
    print(f"  - {m.get('id')}")

print(f"\n所有模型ID（用于筛选）:")
for mid in all_ids:
    print(f"  {mid}")
