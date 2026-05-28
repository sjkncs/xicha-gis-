# -*- coding: utf-8 -*-
"""
VLM 地图分析管线 - 使用 NVIDIA Llama-3.2-90B-Vision 分析高德静态地图
基于 NVIDIA NIM API，支持批量处理，提取步行可达性指标

推荐模型:
  1. meta/llama-3.2-90b-vision-instruct  [主用-高精度]
  2. meta/llama-3.2-11b-vision-instruct  [备用-较快]
  3. meta/llama-3.2-90b-vision-instruct (推理模式)

使用方法:
  # 单张图像分析
  python vlm_map_analysis.py --image "path/to/image.png"

  # 批量分析（已有图像目录）
  python vlm_map_analysis.py --input "data/dl_pipeline/images/raw" --output "vlm_results.csv"

  # 完整pipeline（采样+下载+VLM分析）
  python vlm_map_analysis.py --mode full --sample-max 50

  # 快速测试（3张图像）
  python vlm_map_analysis.py --mode test --sample-max 3
"""

import os
import re
import json
import time
import base64
import random
import argparse
import requests
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading
import io

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ============================================================
# API 配置
# ============================================================

NVAPI_KEYS = [
    key.strip()
    for key in os.environ.get(
        'NVIDIA_API_KEYS',
        os.environ.get('NVIDIA_API_KEY', ''),
    ).split(',')
    if key.strip()
]
BASE_URL = 'https://integrate.api.nvidia.com/v1/chat/completions'

VLM_MODELS = [
    'meta/llama-3.2-90b-vision-instruct',
    'meta/llama-3.2-11b-vision-instruct',
]

# 分析提示词
PROMPT_WALKABILITY = """You are an expert in urban planning and walkability analysis. Analyze this city map screenshot and provide structured urban metrics. IMPORTANT: Output ONLY plain text, NO markdown formatting, NO bold, NO code blocks. Just the raw values.

IMAGE ANALYSIS TASK:
Examine the map image and estimate the following metrics (plain text only):

SCR=0.00 to 1.00 (Sidewalk Coverage Ratio)
GVR=0.00 to 1.00 (Green Visibility Ratio)
VVR=0.00 to 1.00 (Vehicle View Ratio)
CSR=0.00 to 1.00 (Building/Sky Ratio)
UrbanForm=High-Rise or Mid-Rise or Low-Rise or Open
BldDensity=0 to 100 percent
RoadWidth=1 to 5 (1=narrow, 5=wide)
GreenPct=0 to 100 percent
PedScore=1 to 5 (walkability)
LandUse=Residential or Commercial or Industrial or Mixed-Use or Open/Green

Example output format (plain text, no markdown):
SCR=0.65
GVR=0.30
VVR=0.20
CSR=0.45
UrbanForm=Mid-Rise
BldDensity=60%
RoadWidth=3
GreenPct=20%
PedScore=3
LandUse=Mixed-Use"""

PROMPT_SIMPLE = """Describe the key urban elements visible in this city map image. List: buildings (height estimate), roads, green space, water bodies, sky visibility. Be concise (50 words)."""


# ============================================================
# 数据结构
# ============================================================

@dataclass
class VLMAnalysisResult:
    image_path: str = ''
    sample_id: str = ''
    model: str = ''
    timestamp: str = ''

    scr: float = 0.0
    gvr: float = 0.0
    vvr: float = 0.0
    csr: float = 0.0
    urban_form: str = ''
    bld_density: float = 0.0
    road_width: int = 0
    green_pct: float = 0.0
    ped_score: int = 0
    land_use: str = ''

    raw_response: str = ''
    proc_time_ms: float = 0.0
    error: str = ''

    def is_valid(self) -> bool:
        return bool(self.raw_response) and not self.error


# ============================================================
# VLM 客户端
# ============================================================

class VLMMapAnalyzer:
    """NVIDIA VLM 地图分析客户端（支持多Key负载均衡）"""

    def __init__(
        self,
        api_keys: List[str] = None,
        models: List[str] = None,
        base_url: str = BASE_URL,
        max_retries: int = 3,
        timeout: int = 120,
    ):
        self.api_keys = api_keys or NVAPI_KEYS
        self.models = models or VLM_MODELS
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self._key_idx = 0
        self._lock = threading.Lock()

        # 验证 API
        self._validate_keys()

    def _get_key(self) -> str:
        with self._lock:
            key = self.api_keys[self._key_idx % len(self.api_keys)]
            self._key_idx += 1
            return key

    def _get_model(self) -> str:
        return self.models[0]  # 优先用最强的模型

    def _validate_keys(self):
        """验证 API key"""
        print(f'Validating {len(self.api_keys)} API keys...')
        valid_keys = []
        for key in self.api_keys:
            try:
                resp = requests.post(
                    self.base_url,
                    headers={
                        'Authorization': f'Bearer {key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'model': 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
                        'messages': [{'role': 'user', 'content': 'hi'}],
                        'max_tokens': 5,
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    valid_keys.append(key)
                    print(f'  [OK] Key {key[:12]}***')
                else:
                    print(f'  [FAIL] Key {key[:12]}*** status={resp.status_code}')
            except Exception as e:
                print(f'  [FAIL] Key {key[:12]}*** {e}')

        if not valid_keys:
            raise RuntimeError('No valid API keys found!')
        self.api_keys = valid_keys
        print(f'  Valid keys: {len(valid_keys)}')

    def _call_vlm(self, image_path: str, prompt: str = None) -> Dict[str, Any]:
        """调用 VLM API"""
        prompt = prompt or PROMPT_WALKABILITY
        model = self._get_model()
        key = self._get_key()

        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')

        messages = [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{img_b64}'},
                    },
                ],
            }
        ]

        payload = {
            'model': model,
            'messages': messages,
            'max_tokens': 512,
            'temperature': 0.1,
        }

        headers = {
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
        }

        for attempt in range(self.max_retries):
            try:
                t0 = time.time()
                resp = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
                elapsed = (time.time() - t0) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    msg = data.get('choices', [{}])[0].get('message', {})
                    content = msg.get('content', '').strip()
                    return {
                        'ok': True,
                        'content': content,
                        'model': model,
                        'proc_time_ms': elapsed,
                        'error': '',
                    }
                elif resp.status_code == 429:
                    time.sleep(5 * (attempt + 1))
                    continue
                else:
                    err = resp.json() if resp.text else {}
                    return {
                        'ok': False,
                        'content': '',
                        'model': model,
                        'proc_time_ms': elapsed,
                        'error': f'status={resp.status_code}: {str(err)[:100]}',
                    }
            except requests.exceptions.Timeout:
                if attempt < self.max_retries - 1:
                    time.sleep(3)
                    continue
                return {
                    'ok': False,
                    'content': '',
                    'model': model,
                    'proc_time_ms': 0,
                    'error': 'timeout',
                }
            except Exception as e:
                return {
                    'ok': False,
                    'content': '',
                    'model': model,
                    'proc_time_ms': 0,
                    'error': str(e)[:100],
                }

        return {
            'ok': False,
            'content': '',
            'model': model,
            'proc_time_ms': 0,
            'error': 'max retries exceeded',
        }

    def analyze(self, image_path: str, sample_id: str = '') -> VLMAnalysisResult:
        """分析单张地图图像"""
        t0 = time.time()

        if not os.path.exists(image_path):
            return VLMAnalysisResult(
                image_path=image_path,
                sample_id=sample_id,
                error='file_not_found',
                proc_time_ms=(time.time() - t0) * 1000,
            )

        sample_id = sample_id or Path(image_path).stem
        resp_data = self._call_vlm(image_path, PROMPT_WALKABILITY)
        content = resp_data.get('content', '')
        raw_response = content
        error = resp_data.get('error', '')

        # GVR patterns (zero-or-more spaces after = or :)
        gvr = self._extract_float(content, r'GVR[=:\s]*([\d.]+)')
        if gvr == 0.0:
            gvr = self._extract_float(content, r'\*\*GVR[^:]*:\s*([\d.]+)\*\*', default=0.0)
        if gvr == 0.0:
            gvr = self._extract_float(content, r'GVR[^a-z][^:]*:\s*([\d.]+)', default=0.0)
        if gvr == 0.0:
            gvr = self._extract_float(content, r'Green\s+View\s+Ratio[^:]*:\s*([\d.]+)', default=0.0)
        if gvr == 0.0:
            gvr = self._extract_float(content, r'Grid\s+Versus\s+Radial[^:]*:\s*([\d.]+)', default=0.0)

        # VVR patterns
        vvr = self._extract_float(content, r'VVR[=:\s]*([\d.]+)')
        if vvr == 0.0:
            vvr = self._extract_float(content, r'\*\*VVR[^:]*:\s*([\d.]+)\*\*', default=0.0)
        if vvr == 0.0:
            vvr = self._extract_float(content, r'Vehicle[^a-z][^:]*:\s*([\d.]+)', default=0.0)
        if vvr == 0.0:
            vvr = self._extract_float(content, r'Vehicular\s+Versus\s+Pedestrian[^:]*:\s*([\d.]+)', default=0.0)

        # CSR patterns
        csr = self._extract_float(content, r'CSR[=:\s]*([\d.]+)')
        if csr == 0.0:
            csr = self._extract_float(content, r'\*\*CSR[^:]*:\s*([\d.]+)\*\*', default=0.0)
        if csr == 0.0:
            csr = self._extract_float(content, r'Compactness[^:]*:\s*([\d.]+)', default=0.0)
        if csr == 0.0:
            csr = self._extract_float(content, r'City\s+Shape\s+Ratio[^:]*:\s*([\d.]+)', default=0.0)

        # SCR patterns
        scr = self._extract_float(content, r'SCR[=:\s]*([\d.]+)')
        if scr == 0.0:
            scr = self._extract_float(content, r'\*\*SCR[^:]*:\s*([\d.]+)\*\*', default=0.0)
        if scr == 0.0:
            scr = self._extract_float(content, r'Street\s+Connectivity[^:]*:\s*([\d.]+)', default=0.0)
        if scr == 0.0:
            scr = self._extract_float(content, r'Street\s+Closure\s+Ratio[^:]*:\s*([\d.]+)', default=0.0)

        bld_density = self._extract_float(content, r'BldDensity[=:\s]*(\d+)%?', default=0.0, clamp=False)
        if bld_density == 0.0:
            bld_density = self._extract_float(content, r'\*\*Building\s+Density[^:]*:\s*(\d+)%?', default=0.0, clamp=False)

        green_pct = self._extract_float(content, r'GreenPct[=:\s]*(\d+)%?', default=0.0, clamp=False)
        if green_pct == 0.0:
            green_pct = self._extract_float(content, r'\*\*Green\s+Space[^:]*:\s*(\d+)%?', default=0.0, clamp=False)

        road_width = self._extract_int(content, r'RoadWidth[=:\s]*(\d+)', default=0)
        if road_width == 0:
            road_width = self._extract_int(content, r'\*\*Road\s+Width[^:]*:\s*(\d+)', default=0)

        ped_score = self._extract_int(content, r'PedScore[=:\s]*(\d+)', default=0)
        if ped_score == 0:
            ped_score = self._extract_int(content, r'\*\*Pedestrian[^:]*:\s*(\d+)', default=0)

        urban_forms = re.findall(
            r'UrbanForm[=:\s]*([\w\-]+)',
            content,
            re.IGNORECASE,
        )
        # Filter to valid values
        valid_forms = {'High-Rise', 'Mid-Rise', 'Low-Rise', 'Open', 'Open-Other', 'Other'}
        urban_form = ''
        for f in urban_forms:
            f_clean = f.strip()
            if f_clean in valid_forms or f_clean.replace('-', '').replace(' ', '') in ['HighRise', 'MidRise', 'LowRise']:
                urban_form = f_clean
                break
            if 'high' in f_clean.lower() and 'rise' in f_clean.lower():
                urban_form = 'High-Rise'
                break
            if 'mid' in f_clean.lower() and 'rise' in f_clean.lower():
                urban_form = 'Mid-Rise'
                break
            if 'low' in f_clean.lower() and 'rise' in f_clean.lower():
                urban_form = 'Low-Rise'
                break
            if 'open' in f_clean.lower():
                urban_form = 'Open'
                break

        land_uses = re.findall(
            r'LandUse[=:\s]*([\w/\-]+)',
            content,
            re.IGNORECASE,
        )
        land_use = land_uses[0].strip() if land_uses else ''

        return VLMAnalysisResult(
            image_path=image_path,
            sample_id=sample_id,
            model=resp_data.get('model', ''),
            timestamp=datetime.now().isoformat(),
            scr=scr,
            gvr=gvr,
            vvr=vvr,
            csr=csr,
            urban_form=urban_form,
            bld_density=bld_density,
            road_width=road_width,
            green_pct=green_pct,
            ped_score=ped_score,
            land_use=land_use,
            raw_response=raw_response,
            proc_time_ms=resp_data.get('proc_time_ms', 0) or (time.time() - t0) * 1000,
            error=error,
        )

    @staticmethod
    def _extract_float(text: str, pattern: str, default: float = 0.0, clamp: bool = True) -> float:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                val = float(match.group(1))
                if clamp:
                    val = max(0.0, min(1.0, val))
                return val
            except (ValueError, IndexError):
                pass
        return default

    @staticmethod
    def _extract_int(text: str, pattern: str, default: int = 0) -> int:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
        return default

    def batch_analyze(
        self,
        image_paths: List[str],
        sample_ids: List[str] = None,
        max_workers: int = 2,
        rate_limit: float = 1.0,
    ) -> List[VLMAnalysisResult]:
        """批量分析图像（多线程）"""
        n = len(image_paths)
        sample_ids = sample_ids or [''] * n

        results = []
        total = len(image_paths)
        lock = threading.Lock()
        completed = [0]

        def analyze_one(idx: int) -> VLMAnalysisResult:
            img_path = image_paths[idx]
            sid = sample_ids[idx] if idx < len(sample_ids) else ''
            result = self.analyze(img_path, sid)

            with lock:
                completed[0] += 1
                done = completed[0]
                if done % 5 == 0 or done == total:
                    print(f'  [{done}/{total}] {Path(img_path).name} | '
                          f'SCR={result.scr:.2f} GVR={result.gvr:.2f} '
                          f'VVR={result.vvr:.2f} CSR={result.csr:.2f} '
                          f'| {result.urban_form or result.error or "OK"}')

            time.sleep(rate_limit)
            return result

        print(f'Starting batch analysis: {n} images, {max_workers} workers')
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(analyze_one, i): i for i in range(n)
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    idx = futures[future]
                    results.append(VLMAnalysisResult(
                        image_path=image_paths[idx],
                        sample_id=sample_ids[idx] if idx < len(sample_ids) else '',
                        error=str(e),
                    ))

        elapsed = time.time() - t0
        valid = sum(1 for r in results if r.is_valid())
        print(f'Batch done: {valid}/{n} valid, {elapsed:.0f}s, {elapsed/n:.1f}s/image')

        return results


# ============================================================
# 辅助函数
# ============================================================

def find_images(input_path: str) -> List[str]:
    """从路径找图像文件"""
    if os.path.isfile(input_path):
        if input_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
            return [input_path]
        return []

    if os.path.isdir(input_path):
        images = []
        for ext in ['png', 'jpg', 'jpeg', 'bmp', 'webp']:
            images.extend(Path(input_path).glob(f'*.{ext}'))
            images.extend(Path(input_path).glob(f'*.{ext.upper()}'))
        return [str(p) for p in sorted(images)]

    return []


def extract_sample_id(image_path: str) -> str:
    """从图像路径提取 sample_id"""
    stem = Path(image_path).stem
    match = re.search(r'(SMP_\d+|[A-Z0-9]{6,})', stem)
    if match:
        return match.group(1)
    return stem


def save_results_csv(results: List[VLMAnalysisResult], output_path: str):
    """保存结果为 CSV"""
    if not HAS_PANDAS:
        print('[WARN] pandas not available, saving JSON only')
        return save_results_json(results, output_path.replace('.csv', '.json'))

    rows = []
    for r in results:
        rows.append({
            'image_path': r.image_path,
            'sample_id': r.sample_id,
            'model': r.model,
            'timestamp': r.timestamp,
            'SCR': r.scr,
            'GVR': r.gvr,
            'VVR': r.vvr,
            'CSR': r.csr,
            'urban_form': r.urban_form,
            'bld_density_pct': r.bld_density,
            'road_width': r.road_width,
            'green_pct': r.green_pct,
            'ped_score': r.ped_score,
            'land_use': r.land_use,
            'proc_time_ms': r.proc_time_ms,
            'error': r.error,
            'raw_response': r.raw_response[:500] if r.raw_response else '',
        })

    df = pd.DataFrame(rows)
    csv_path = output_path
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'CSV saved: {csv_path} ({len(df)} rows)')

    # 保存带完整原始响应的 JSON
    json_path = output_path.replace('.csv', '.json')
    save_results_json(results, json_path)


def save_results_json(results: List[VLMAnalysisResult], output_path: str):
    """保存结果为 JSON"""
    data = [asdict(r) for r in results]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'JSON saved: {output_path}')


def print_summary(results: List[VLMAnalysisResult]):
    """打印结果摘要"""
    valid = [r for r in results if r.is_valid()]
    if not valid:
        print('\n[ERROR] No valid results!')
        return

    df_valid = pd.DataFrame([asdict(r) for r in valid])

    print('\n' + '=' * 60)
    print('VLM Walkability Analysis Summary')
    print('=' * 60)

    for col, label in [
        ('scr', 'SCR (Sidewalk Coverage)'),
        ('gvr', 'GVR (Green Visibility)'),
        ('vvr', 'VVR (Vehicle View)'),
        ('csr', 'CSR (Building/Sky Ratio)'),
        ('bld_density', 'Building Density (%)'),
        ('green_pct', 'Green Space (%)'),
        ('road_width', 'Road Width (1-5)'),
        ('ped_score', 'Pedestrian Score (1-5)'),
    ]:
        if col in df_valid.columns:
            vals = df_valid[col].dropna().astype(float)
            if len(vals) > 0:
                print(f'  {label:30s}: mean={vals.mean():.3f} '
                      f'min={vals.min():.3f} max={vals.max():.3f}')

    print()
    if 'urban_form' in df_valid.columns:
        print('  Urban Form distribution:')
        for form, cnt in df_valid['urban_form'].value_counts().items():
            print(f'    {form}: {cnt} ({cnt/len(df_valid)*100:.0f}%)')

    if 'land_use' in df_valid.columns:
        print('  Land Use distribution:')
        for lu, cnt in df_valid['land_use'].value_counts().items():
            if lu:
                print(f'    {lu}: {cnt} ({cnt/len(df_valid)*100:.0f}%)')


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='VLM 地图分析 - NVIDIA Llama-3.2-90B-Vision',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python vlm_map_analysis.py --input "data/dl_pipeline/images/raw"
  python vlm_map_analysis.py --image "path/to/map.png"
  python vlm_map_analysis.py --input "data/dl_pipeline/images/raw" --output "vlm_results.csv"
  python vlm_map_analysis.py --mode test --sample-max 3
        '''
    )

    parser.add_argument('--image', help='Single image path')
    parser.add_argument('--input', help='Input directory or file')
    parser.add_argument('--output', default='vlm_walkability_results.csv',
                        help='Output CSV path')
    parser.add_argument('--sample-max', type=int, default=10,
                        help='Max images to process')
    parser.add_argument('--workers', type=int, default=1,
                        help='Concurrent workers (1=sequential, 2+=parallel)')
    parser.add_argument('--rate-limit', type=float, default=2.0,
                        help='Seconds between requests (avoid rate limit)')
    parser.add_argument('--timeout', type=int, default=120,
                        help='API timeout (seconds)')
    parser.add_argument('--prompt', default='walkability',
                        choices=['walkability', 'simple'],
                        help='Analysis prompt type')
    parser.add_argument('--model', default='meta/llama-3.2-90b-vision-instruct',
                        help='VLM model to use')
    parser.add_argument('--no-skip', action='store_true',
                        help='Re-analyze even if output CSV exists')

    args = parser.parse_args()

    # 确定输入
    if args.image:
        image_paths = [args.image]
    elif args.input:
        image_paths = find_images(args.input)
    else:
        # 默认使用 dl_pipeline 目录
        default_dir = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\dl_pipeline\images\raw'
        image_paths = find_images(default_dir)
        if not image_paths:
            print(f'[ERROR] No images found in {default_dir}')
            return

    if not image_paths:
        print('[ERROR] No images found!')
        return

    # 限制数量
    if args.sample_max and len(image_paths) > args.sample_max:
        image_paths = image_paths[:args.sample_max]
        print(f'[INFO] Limited to {args.sample_max} images')

    print(f'Processing {len(image_paths)} images...')

    # 跳过已处理的
    if not args.no_skip and os.path.exists(args.output) and HAS_PANDAS:
        existing = pd.read_csv(args.output)
        done_ids = set(existing['image_path'].tolist())
        skipped = [p for p in image_paths if p in done_ids]
        image_paths = [p for p in image_paths if p not in done_ids]
        print(f'[INFO] Skipped {len(skipped)} already-processed images')

    if not image_paths:
        print('[INFO] All images already processed!')
        return

    # 初始化分析器
    analyzer = VLMMapAnalyzer(
        api_keys=NVAPI_KEYS,
        models=[args.model],
        timeout=args.timeout,
    )

    # 批量分析
    sample_ids = [extract_sample_id(p) for p in image_paths]
    results = analyzer.batch_analyze(
        image_paths,
        sample_ids=sample_ids,
        max_workers=args.workers,
        rate_limit=args.rate_limit,
    )

    # 保存结果
    save_results_csv(results, args.output)

    # 摘要
    print_summary(results)


if __name__ == '__main__':
    main()
