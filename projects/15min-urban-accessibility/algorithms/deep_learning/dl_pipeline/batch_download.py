# -*- coding: utf-8 -*-
"""
批量下载脚本 - 高德静态地图 + 街景
断点续传 + 500配额管理 + 多分辨率支持

API配额: 500次/日
- 静态地图: 每个采样点 × 多分辨率
- 每张图消耗 1 次配额

配额分配策略（500次）:
  静态地图 300张 → 预留 300次
  备用（失败重试/验证） 200次
"""

import os
import sys
import json
import time
import math
import random
import hashlib
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import numpy as np
import pandas as pd

try:
    import requests
except ImportError:
    print('请安装 requests: pip install requests')
    sys.exit(1)


# ============================================================
# 路径配置
# ============================================================

BASE_DIR = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
DATA_DIR = os.path.join(BASE_DIR, 'data', 'dl_pipeline')
IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'raw')
CHECKPOINT_DIR = os.path.join(DATA_DIR, 'checkpoints')
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

AMAP_KEY = (
    os.environ.get('AMAP_API_KEY')
    or os.environ.get('GAODE_API_KEY')
    or ''
).strip()
AMAP_DAILY_QUOTA = 500  # 每日总配额
RESERVED_QUOTA = 200    # 预留配额（备用/重试）


# ============================================================
# 坐标转换
# ============================================================

PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323


def _tlat(x, y):
    ret = -100.0 + 2.0*x + 3.0*y + 0.2*y*y + 0.1*x*y + 0.2*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI))*2.0/3.0
    ret += (20.0*math.sin(y*PI) + 40.0*math.sin(y/3.0*PI))*2.0/3.0
    ret += (160.0*math.sin(y/12.0*PI) + 320.0*math.sin(y*PI/30.0))*2.0/3.0
    return ret


def _tlng(x, y):
    ret = 300.0 + x + 2.0*y + 0.1*x*x + 0.1*x*y + 0.1*math.sqrt(abs(x))
    ret += (20.0*math.sin(6.0*x*PI) + 20.0*math.sin(2.0*x*PI))*2.0/3.0
    ret += (20.0*math.sin(x*PI) + 40.0*math.sin(x/3.0*PI))*2.0/3.0
    ret += (150.0*math.sin(x/12.0*PI) + 300.0*math.sin(x/30.0*PI))*2.0/3.0
    return ret


def wgs84_to_gcj02(lng: float, lat: float) -> Tuple[float, float]:
    """WGS84 -> GCJ-02 (高德坐标)"""
    dlat = _tlat(lng - 105.0, lat - 35.0)
    dlng = _tlng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlng = (dlng * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    return lng + dlng, lat + dlat


# ============================================================
# 配额管理
# ============================================================

@dataclass
class QuotaManager:
    """
    高德 API 配额管理器

    特性:
    - 每日配额上限
    - 进程内计数器
    - 断点恢复（从文件读取历史使用量）
    - 速率限制（每秒请求数）
    """
    key: str
    daily_quota: int = AMAP_DAILY_QUOTA
    reserved: int = RESERVED_QUOTA
    requests_per_second: float = 5.0  # 高德 Web 服务一般 5-10 QPS

    _used: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _last_request_time: float = field(default=0.0, init=False)
    _checkpoint_file: str = field(default='', init=False)

    def __post_init__(self):
        # checkpoint 文件路径
        today = datetime.now().strftime('%Y%m%d')
        self._checkpoint_file = os.path.join(
            CHECKPOINT_DIR, f'amap_quota_{self.key[-6:]}_{today}.json'
        )
        self._load_checkpoint()

    def _load_checkpoint(self):
        """从文件恢复今日使用量"""
        if os.path.exists(self._checkpoint_file):
            try:
                with open(self._checkpoint_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                saved_date = data.get('date', '')
                today = datetime.now().strftime('%Y%m%d')
                if saved_date == today:
                    self._used = data.get('used', 0)
                    print(f'  [配额] 从断点恢复: 已用 {self._used}/{self.daily_quota}')
                else:
                    self._used = 0
                    print(f'  [配额] 新的一天，清零配额计数')
            except Exception:
                self._used = 0

    def _save_checkpoint(self):
        """保存使用量到文件"""
        try:
            with open(self._checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'date': datetime.now().strftime('%Y%m%d'),
                    'used': self._used,
                    'key_suffix': self.key[-6:],
                }, f, ensure_ascii=False)
        except Exception:
            pass

    @property
    def remaining(self) -> int:
        return max(0, self.daily_quota - self._used)

    @property
    def can_request(self) -> bool:
        return self._used < self.daily_quota - self.reserved

    def record(self, count: int = 1):
        """记录一次请求"""
        with self._lock:
            self._used += count
            self._save_checkpoint()

    def wait_if_needed(self):
        """如果请求过快，等待"""
        with self._lock:
            now = time.time()
            min_interval = 1.0 / self.requests_per_second
            elapsed = now - self._last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self._last_request_time = time.time()


# ============================================================
# 静态地图 API
# ============================================================

@dataclass
class StaticMapResult:
    success: bool
    file_path: str = ''
    size_bytes: int = 0
    error: str = ''


class AmapBatchDownloader:
    """
    高德批量静态地图下载器

    功能:
    - 断点续传（跳过已下载的文件）
    - 配额管理（每日500次上限）
    - 多分辨率支持（标准/高清）
    - 多视角支持（不同zoomlevel）
    - 并发控制
    """

    BASE_URL = 'https://restapi.amap.com/v3/staticmap'

    def __init__(
        self,
        key: str = AMAP_KEY,
        quota: int = AMAP_DAILY_QUOTA,
        reserved: int = RESERVED_QUOTA,
        zoom: int = 16,
        width: int = 600,
        height: int = 400,
        scale: int = 1,
        workers: int = 3,
        output_dir: str = IMAGES_DIR,
    ):
        self.key = key
        self.quota = QuotaManager(key, daily_quota=quota, reserved=reserved)
        self.zoom = zoom
        self.width = width
        self.height = height
        self.scale = scale
        self.workers = workers
        self.output_dir = output_dir
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; GIS Research Bot/1.0)',
        })

    def _get_output_path(self, lng: float, lat: float, tag: str = '') -> str:
        """生成输出文件路径"""
        coord_str = f"{lng:.6f}_{lat:.6f}"
        hash_str = hashlib.md5(coord_str.encode()).hexdigest()[:8]
        filename = f"{tag}{'_' if tag else ''}z{self.zoom}_w{self.width}_h{self.height}_{hash_str}.png"
        return os.path.join(self.output_dir, filename)

    def download_single(
        self,
        lng: float,
        lat: float,
        tag: str = '',
        skip_existing: bool = True,
    ) -> StaticMapResult:
        """
        下载单张静态地图

        参数:
            lng, lat: WGS84 坐标
            tag: 文件名前缀
            skip_existing: 是否跳过已存在的文件

        返回:
            StaticMapResult
        """
        gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
        output_path = self._get_output_path(lng, lat, tag)

        if skip_existing and os.path.exists(output_path):
            fsize = os.path.getsize(output_path)
            if fsize > 1000:
                return StaticMapResult(
                    success=True, file_path=output_path, size_bytes=fsize,
                    error='skip_existing'
                )

        # 速率控制
        self.quota.wait_if_needed()

        if not self.quota.can_request:
            return StaticMapResult(
                success=False, error=f'quota_exhausted: 剩余 {self.quota.remaining}/{self.quota.daily_quota}'
            )

        params = {
            'key': self.key,
            'location': f'{gcj_lng:.6f},{gcj_lat:.6f}',
            'zoom': self.zoom,
            'size': f'{self.width}*{self.height}',
            'scale': self.scale,
            'traffic': 0,
        }

        try:
            resp = self._session.get(self.BASE_URL, params=params, timeout=15)
            ct = resp.headers.get('Content-Type', '')

            if resp.status_code == 200 and (
                'image' in ct or
                resp.content[:3] == b'\xff\xd8\xff' or
                b'PNG' in resp.content[:10]
            ):
                if len(resp.content) > 500:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(resp.content)
                    self.quota.record()
                    return StaticMapResult(
                        success=True, file_path=output_path,
                        size_bytes=len(resp.content)
                    )
                else:
                    return StaticMapResult(success=False, error='image_too_small')

            # 尝试解析错误
            try:
                err = resp.json()
                err_msg = err.get('info', str(err))
                self.quota.record()
                return StaticMapResult(success=False, error=f'api_error: {err_msg}')
            except Exception:
                return StaticMapResult(
                    success=False,
                    error=f'http_{resp.status_code}_unknown_response'
                )

        except requests.exceptions.Timeout:
            return StaticMapResult(success=False, error='timeout')
        except requests.exceptions.RequestException as e:
            return StaticMapResult(success=False, error=f'request_error: {e}')
        except Exception as e:
            return StaticMapResult(success=False, error=f'unknown_error: {e}')

    def batch_download(
        self,
        samples: Union[pd.DataFrame, List[Dict]],
        tag: str = '',
        resume: bool = True,
        delay: float = 0.0,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """
        批量下载

        参数:
            samples: DataFrame 或列表，含 lng/lat 列
            tag: 文件名前缀
            resume: 断点续传
            delay: 每次请求间延迟（秒）
            verbose: 打印进度

        返回:
            下载结果统计
        """
        print('=' * 60)
        print('高德静态地图批量下载')
        print('=' * 60)
        print(f'  API Key: {self.key[:8]}...{self.key[-4:]}')
        print(f'  每日配额: {self.quota.daily_quota}')
        print(f'  预留余量: {self.quota.reserved}')
        print(f'  分辨率: {self.width}x{self.height} @ scale={self.scale}')
        print(f'  Zoom: {self.zoom}')
        print(f'  输出目录: {self.output_dir}')

        # 提取坐标
        if isinstance(samples, pd.DataFrame):
            records = samples[['lng', 'lat']].to_dict(orient='records')
        else:
            records = samples

        print(f'\n  总采样点: {len(records)}')
        print(f'  当前配额状态: 已用 {self.quota._used}/{self.quota.daily_quota}')

        # 统计已有文件
        existing = 0
        for r in records:
            path = self._get_output_path(r['lng'], r['lat'], tag)
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                existing += 1
        print(f'  已存在: {existing} 张（将跳过）')

        to_download = [r for r in records
                       if not (resume and os.path.exists(self._get_output_path(r['lng'], r['lat'], tag))
                               and os.path.getsize(self._get_output_path(r['lng'], r['lat'], tag)) > 1000)]

        print(f'  待下载: {len(to_download)} 张')
        print()

        if len(to_download) == 0:
            print('[完成] 无需下载')
            return {'total': len(records), 'downloaded': existing, 'failed': 0}

        if not self.quota.can_request:
            print(f'[错误] 配额不足（剩余 {self.quota.remaining}）')
            return {'total': len(records), 'downloaded': existing, 'failed': len(to_download)}

        # 下载
        results = []
        downloaded = existing
        failed = 0
        errors = {}

        print('开始下载...')
        for i, r in enumerate(to_download):
            # 进度报告
            if verbose and (i + 1) % 20 == 0:
                pct = (i + 1) / len(to_download) * 100
                rem = (len(to_download) - i - 1) * delay if delay > 0 else 0
                print(f'  进度 {i+1}/{len(to_download)} ({pct:.0f}%) | '
                      f'配额: {self.quota._used}/{self.quota.daily_quota} | '
                      f'成功: {downloaded} | 失败: {failed} | '
                      f'剩余时间约: {rem/60:.0f}min')

            # 配额耗尽检查
            if not self.quota.can_request:
                print(f'\n[停止] 配额接近上限（{self.quota._used}/{self.quota.daily_quota}），停止下载')
                print(f'  剩余 {len(to_download) - i} 个点未下载')
                break

            result = self.download_single(r['lng'], r['lat'], tag=tag, skip_existing=resume)

            if result.success:
                downloaded += 1
            else:
                failed += 1
                err_key = result.error
                errors[err_key] = errors.get(err_key, 0) + 1

            if delay > 0:
                time.sleep(delay)

            # 每50张保存一次checkpoint
            if (i + 1) % 50 == 0:
                self._save_batch_checkpoint(records, downloaded, failed)

        # 保存最终结果
        self._save_batch_checkpoint(records, downloaded, failed)

        print()
        print('=' * 60)
        print('下载完成')
        print(f'  总计: {len(records)}')
        print(f'  成功: {downloaded} (含已有: {existing})')
        print(f'  失败: {failed}')
        print(f'  配额已用: {self.quota._used}/{self.quota.daily_quota}')
        print(f'  剩余配额: {self.quota.remaining}')
        if errors:
            print(f'  错误类型:')
            for err, cnt in sorted(errors.items(), key=lambda x: -x[1]):
                print(f'    {err}: {cnt}')

        return {
            'total': len(records),
            'downloaded': downloaded,
            'failed': failed,
            'existing': existing,
            'quota_used': self.quota._used,
            'quota_remaining': self.quota.remaining,
            'errors': errors,
        }

    def _save_batch_checkpoint(self, records: List[Dict], downloaded: int, failed: int):
        """保存批处理断点"""
        ckpt = {
            'date': datetime.now().isoformat(),
            'total': len(records),
            'downloaded': downloaded,
            'failed': failed,
            'quota_used': self.quota._used,
        }
        ckpt_path = os.path.join(CHECKPOINT_DIR, f'download_ckpt_{datetime.now().strftime("%Y%m%d")}.json')
        try:
            with open(ckpt_path, 'w', encoding='utf-8') as f:
                json.dump(ckpt, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='高德静态地图批量下载')
    parser.add_argument('--input', default=None,
                        help='采样点 CSV/JSON 路径（默认使用 prepare_samples 生成的）')
    parser.add_argument('--tag', default='amap',
                        help='文件名前缀')
    parser.add_argument('--zoom', type=int, default=16,
                        help='地图缩放级别 (1-18)')
    parser.add_argument('--width', type=int, default=600,
                        help='图片宽度 (最大1024)')
    parser.add_argument('--height', type=int, default=400,
                        help='图片高度 (最大1024)')
    parser.add_argument('--scale', type=int, default=1, choices=[1, 2],
                        help='屏幕scale (1=标准, 2=高清)')
    parser.add_argument('--workers', type=int, default=3,
                        help='并发线程数')
    parser.add_argument('--delay', type=float, default=0.3,
                        help='请求间隔（秒）')
    parser.add_argument('--output', default=IMAGES_DIR,
                        help='输出目录')
    parser.add_argument('--no-resume', action='store_true',
                        help='禁用断点续传（重新下载全部）')

    args = parser.parse_args()

    # 加载采样点
    if args.input:
        input_path = args.input
    else:
        input_path = os.path.join(SAMPLES_DIR, 'dl_sample_points.csv')

    if not os.path.exists(input_path):
        print(f'[错误] 采样点文件不存在: {input_path}')
        print('请先运行: python prepare_samples.py')
        sys.exit(1)

    print(f'加载采样点: {input_path}')
    if input_path.endswith('.json'):
        with open(input_path, 'r', encoding='utf-8') as f:
            samples = pd.DataFrame(json.load(f))
    else:
        samples = pd.read_csv(input_path)

    print(f'  采样点数: {len(samples)}')

    # 创建下载器
    downloader = AmapBatchDownloader(
        key=AMAP_KEY,
        quota=AMAP_DAILY_QUOTA,
        reserved=RESERVED_QUOTA,
        zoom=args.zoom,
        width=args.width,
        height=args.height,
        scale=args.scale,
        workers=args.workers,
        output_dir=args.output,
    )

    # 执行下载
    result = downloader.batch_download(
        samples=samples,
        tag=args.tag,
        resume=not args.no_resume,
        delay=args.delay,
        verbose=True,
    )

    # 保存结果
    result_path = os.path.join(CHECKPOINT_DIR, f'download_result_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f'\n结果已保存: {result_path}')

    # 汇总已有图像
    print('\n汇总:')
    img_files = [f for f in os.listdir(args.output) if f.endswith('.png')]
    print(f'  目录 {args.output} 中现有图像: {len(img_files)} 张')


if __name__ == '__main__':
    main()
