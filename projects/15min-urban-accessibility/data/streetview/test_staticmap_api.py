# -*- coding: utf-8 -*-
"""测试高德静态地图API"""

import os
import math
import time
import requests

KEY = (
    os.environ.get('AMAP_API_KEY')
    or os.environ.get('GAODE_API_KEY')
    or ''
).strip()
if not KEY:
    raise RuntimeError('Set AMAP_API_KEY or GAODE_API_KEY before running this script.')
# 深圳南山 科技园附近测试坐标
lng, lat = 113.9412, 22.5308

# GCJ-02 转换
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

def wgs84_to_gcj02(lng, lat):
    dlat = _tlat(lng-105.0, lat-35.0)
    dlng = _tlng(lng-105.0, lat-35.0)
    radlat = lat/180.0*PI
    magic = math.sin(radlat)
    magic = 1 - EE*magic*magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat*180.0)/((A*(1-EE))/(magic*sqrtmagic)*PI)
    dlng = (dlng*180.0)/(A/sqrtmagic*math.cos(radlat)*PI)
    return lng+dlng, lat+dlat

gcj_lng, gcj_lat = wgs84_to_gcj02(lng, lat)
print(f'[坐标] WGS84: ({lng:.6f}, {lat:.6f}) -> GCJ-02: ({gcj_lng:.6f}, {gcj_lat:.6f})')

# 测试静态地图 API
url = 'https://restapi.amap.com/v3/staticmap'
params = {
    'key': KEY,
    'location': f'{gcj_lng:.6f},{gcj_lat:.6f}',
    'zoom': 16,
    'size': '600*400',
    'scale': 1,
    'traffic': 0,
}

print(f'[请求] URL: {url}')
print(f'[请求] params: location={gcj_lng:.6f},{gcj_lat:.6f}, zoom=16, size=600x400')

resp = requests.get(url, params=params, timeout=15)
print(f'[响应] status={resp.status_code}, size={len(resp.content)} bytes')

ct = resp.headers.get('Content-Type', '')
print(f'[响应] Content-Type: {ct}')

is_image = (
    'image' in ct or
    resp.content[:3] == b'\xff\xd8\xff' or
    b'PNG' in resp.content[:10] or
    b'JFIF' in resp.content[:20]
)

if is_image and len(resp.content) > 1000:
    out_dir = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\streetview\integrated_collection\images\amap_staticmap'
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'test_single.png')
    with open(out, 'wb') as f:
        f.write(resp.content)
    print(f'[OK] 图片已保存: {out}')
    print(f'[OK] 文件大小: {os.path.getsize(out)} bytes')
elif len(resp.content) < 5000:
    try:
        err = resp.json()
        print(f'[错误] API返回: {err}')
    except:
        print(f'[错误] 前200字节: {resp.content[:200]}')
else:
    print(f'[未知] 既非图片也非标准错误，长度={len(resp.content)}')
    out_dir = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility\data\streetview\integrated_collection\images\amap_staticmap'
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, 'test_response.bin')
    with open(out, 'wb') as f:
        f.write(resp.content)
    print(f'  已保存原始响应: {out}')
