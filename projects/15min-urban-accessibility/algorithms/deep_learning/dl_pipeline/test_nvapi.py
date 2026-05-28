# -*- coding: utf-8 -*-
"""测试 NVIDIA VLM API 连接"""
import os
import sys

# API 密钥配置
NVAPI_KEYS = [
    key.strip()
    for key in os.environ.get(
        'NVIDIA_API_KEYS',
        os.environ.get('NVIDIA_API_KEY', ''),
    ).split(',')
    if key.strip()
]
BASE_URL = 'https://integrate.api.nvidia.com/v1'
MODEL = 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning'

def test_nvapi(key: str) -> dict:
    """测试单个 API key"""
    import requests

    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }

    payload = {
        'model': MODEL,
        'messages': [
            {
                'role': 'user',
                'content': '请用一句话描述这张图片中的主要元素（天空、建筑、树木、道路等）。只回答类别名称。'
            }
        ],
        'max_tokens': 64,
        'temperature': 0.1,
        'stream': False,
    }

    try:
        resp = requests.post(
            f'{BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=30,
        )
        result = {
            'key': key[:12] + '***',
            'status': resp.status_code,
            'ok': resp.status_code == 200,
        }
        if resp.status_code == 200:
            data = resp.json()
            result['model'] = data.get('model', 'unknown')
            result['content'] = data['choices'][0]['message']['content'][:200]
        else:
            result['error'] = resp.text[:200]
        return result
    except Exception as e:
        return {'key': key[:12] + '***', 'status': 'ERROR', 'ok': False, 'error': str(e)}


def test_image_captioning(key: str, image_path: str) -> dict:
    """测试图像描述（VLM 功能）"""
    import base64
    import requests
    import mimetypes

    with open(image_path, 'rb') as f:
        img_data = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower().lstrip('.')
    mime = mimetypes.types_map.get('.' + ext, 'image/png')

    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }

    payload = {
        'model': MODEL,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': '这是一张城市街景地图截图。请识别并列出图中可见的要素：建筑、绿地、水体、道路、建筑高度（高/中/低密度）等。'
                    },
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:{mime};base64,{img_data[:50000]}'
                        }
                    }
                ]
            }
        ],
        'max_tokens': 256,
        'temperature': 0.1,
        'stream': False,
    }

    try:
        resp = requests.post(
            f'{BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data['choices'][0]['message']['content']
            return {'ok': True, 'content': content[:500]}
        else:
            return {'ok': False, 'error': f'status={resp.status_code}: {resp.text[:200]}'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def test_vlm_on_streetview():
    """测试 VLM 对街景图的分析能力"""
    # 找一张下载的图像
    img_dir = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\dl_pipeline\images\raw'
    files = [f for f in os.listdir(img_dir) if f.endswith('.png')] if os.path.exists(img_dir) else []

    if not files:
        print('[INFO] 没有本地图像，跳过VLM测试')
        return

    # 用第一个可用的 key
    key = NVAPI_KEYS[0]
    img_path = os.path.join(img_dir, files[0])
    print(f'\n使用图像: {files[0]} ({os.path.getsize(img_path)} bytes)')
    print('测试 VLM 图像理解...')

    result = test_image_captioning(key, img_path)
    if result['ok']:
        print(f'[OK] VLM 响应:')
        print(f'  {result["content"]}')
    else:
        print(f'[FAIL] VLM 错误: {result["error"]}')


if __name__ == '__main__':
    print('NVIDIA VLM API 测试')
    print(f'Base URL: {BASE_URL}')
    print(f'Model: {MODEL}')
    print()

    for key in NVAPI_KEYS:
        print(f'测试 Key: {key[:12]}***')
        result = test_nvapi(key)
        if result['ok']:
            print(f'  [OK] status={result["status"]}, model={result["model"]}')
            print(f'  [OK] 内容: {result["content"]}')
        else:
            print(f'  [FAIL] status={result["status"]}')
            if 'error' in result:
                print(f'  [FAIL] {result["error"]}')
        print()

    # VLM 图像理解测试
    print('=' * 50)
    test_vlm_on_streetview()
