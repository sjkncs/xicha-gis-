# -*- coding: utf-8 -*-
"""
P5: 大众点评/美团开放平台 POI 营业时间数据采集

数据来源:
- 美团开放平台: https://open.meituan.com/
- 大众点评: https://open.dianping.com/

注意: 大众点评API已整合至美团开放平台，需企业资质申请。
"""

import pandas as pd
import numpy as np
import os
import sys
import io
import time
import hashlib
import hmac
import requests
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.makedirs(f"{BASE}/data/poi_hours", exist_ok=True)

print("="*70)
print("P5: 大众点评/美团 POI 营业时间采集")
print("="*70)

# ============================================================
# 美团开放平台 API 配置
# ============================================================
class MeituanAPI:
    """美团开放平台 API 客户端"""

    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.getenv('MEITUAN_APP_ID')
        self.app_secret = app_secret or os.getenv('MEITUAN_APP_SECRET')
        self.base_url = "https://open.meituan.com/api"
        self.access_token = None

        if not self.app_id or not self.app_secret:
            print("[!] 未配置美团 API 凭证")
            print("     请设置环境变量:")
            print("     MEITUAN_APP_ID=your_app_id")
            print("     MEITUAN_APP_SECRET=your_app_secret")

    def generate_signature(self, params):
        """
        生成签名 (HMAC-SHA1)

        参数需按字典序排列后与 app_secret 拼接计算签名
        """
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
        sign_str = param_str + self.app_secret
        return hashlib.sha1(sign_str.encode()).hexdigest()

    def search_poi(self, keyword, city='深圳', district='南山区', offset=0, limit=50):
        """
        搜索 POI

        参数:
            keyword: 关键词
            city: 城市
            district: 区县
            offset: 偏移量
            limit: 每页数量
        """
        params = {
            'app_id': self.app_id,
            'timestamp': int(time.time()),
            'city': city,
            'district': district,
            'keyword': keyword,
            'offset': offset,
            'limit': limit,
            'format': 'json',
        }
        params['sign'] = self.generate_signature(params)

        url = f"{self.base_url}/poi/search"
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data
        except Exception as e:
            print(f"[ERROR] API请求失败: {e}")
            return None

    def get_poi_detail(self, poi_id):
        """获取 POI 详情（含营业时间）"""
        params = {
            'app_id': self.app_id,
            'timestamp': int(time.time()),
            'poi_id': poi_id,
            'format': 'json',
        }
        params['sign'] = self.generate_signature(params)

        url = f"{self.base_url}/poi/detail"
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            return data
        except Exception as e:
            print(f"[ERROR] API请求失败: {e}")
            return None


# ============================================================
# 高德地图 WebAPI（推荐 - 无需企业资质）
# ============================================================
class GaodeWebAPI:
    """
    高德地图 Web API

    免费额度: 每日 5000 次请求
    申请地址: https://lbs.amap.com/
    """

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GAODE_API_KEY')
        self.base_url = "https://restapi.amap.com/v3"
        if not self.api_key:
            print("[!] 未配置高德 API Key")
            print("     请申请: https://lbs.amap.com/")

    def search_poi(self, keywords, city='深圳', citylimit='true', offset=20, page=1):
        """
        搜索 POI

        参数:
            keywords: 关键词
            city: 城市
            citylimit: 限制在指定城市
            offset: 每页数量
            page: 页码
        """
        if not self.api_key:
            print("[!] 需要配置 GAODE_API_KEY")
            return None

        params = {
            'key': self.api_key,
            'keywords': keywords,
            'city': city,
            'citylimit': citylimit,
            'offset': offset,
            'page': page,
            'types': self._get_types(keywords),
            'output': 'json',
        }

        url = f"{self.base_url}/place/text"
        try:
            resp = requests.get(url, params=params, timeout=30)
            data = resp.json()
            if data.get('status') == '1':
                pois = data.get('pois', [])
                print(f"  [OK] 获取 {len(pois)} 条 POI")
                return pois
            else:
                print(f"[ERROR] API返回: {data.get('info', '未知错误')}")
                return []
        except Exception as e:
            print(f"[ERROR] 请求失败: {e}")
            return None

    def _get_types(self, keywords):
        """根据关键词返回高德 POI 类型编码"""
        TYPE_MAP = {
            '医院': '090100', '药店': '090101',
            '超市': '100100', '便利店': '100102',
            '银行': '150900', 'ATM': '150904',
            '学校': '150200', '幼儿园': '150201',
            '餐厅': '050100', '美食': '050000',
            '酒店': '100100', '宾馆': '100101',
            'KTV': '080301', '电影院': '080101',
            '健身房': '080400', '公园': '140101',
        }
        for kw, code in TYPE_MAP.items():
            if kw in keywords:
                return code
        return ''


# ============================================================
# 数据采集函数
# ============================================================
def collect_night_service_poi(api_client, categories, output_path):
    """
    采集夜间服务 POI 数据

    参数:
        api_client: API 客户端
        categories: 设施类别列表
        output_path: 输出文件路径
    """
    all_pois = []

    for category in categories:
        print(f"\n[采集] {category}")

        # 搜索 POI
        pois = api_client.search_poi(
            keywords=category,
            city='深圳',
            district='南山区'
        )

        if pois:
            for poi in pois:
                record = {
                    'name': poi.get('name', ''),
                    'address': poi.get('address', ''),
                    'location': poi.get('location', ''),
                    'tel': poi.get('tel', ''),
                    'category': category,
                    'type_code': poi.get('typecode', ''),
                    'biz_ext': poi.get('biz_ext', {}),  # 营业时间可能在此
                    '营业时间': poi.get('营业时间', ''),
                    'indoor': poi.get('indoor', ''),
                    'timestamp': datetime.now().isoformat(),
                }
                all_pois.append(record)

        # 避免请求过快
        time.sleep(0.5)

    # 保存结果
    df = pd.DataFrame(all_pois)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 已保存 {len(df)} 条 POI 到: {output_path}")
    return df


def parse_business_hours(biz_ext_str):
    """
    解析营业时间字符串

    返回:
        dict: {is_24h: bool, night_service: bool, hours: str}
    """
    import re

    result = {
        'is_24h': False,
        'night_service': False,
        'business_hours': '',
        'open_time': '',
        'close_time': '',
        'night_ratio': 0.0
    }

    if not biz_ext_str:
        return result

    biz_ext = json.loads(biz_ext_str) if isinstance(biz_ext_str, str) else biz_ext_str

    # 24小时营业
    if biz_ext.get('opentime'):
        result['business_hours'] = biz_ext['opentime']
        if '24' in str(biz_ext['opentime']):
            result['is_24h'] = True
            result['night_service'] = True
            result['night_ratio'] = 1.0

    # 判断夜间服务 (22:00 - 06:00)
    time_pattern = r'(\d{1,2}):(\d{2})'
    hours = re.findall(time_pattern, result['business_hours'])

    if len(hours) >= 2:
        try:
            open_h, open_m = int(hours[0][0]), int(hours[0][1])
            close_h, close_m = int(hours[-1][0]), int(hours[-1][1])

            open_min = open_h * 60 + open_m
            close_min = close_h * 60 + close_m

            # 计算夜间时段覆盖率
            night_min = 8 * 60  # 8小时夜间
            if close_min > open_min:
                night_covered = max(0, close_min - max(open_min, 22*60))
            else:  # 跨天
                night_covered = max(0, 24*60 - open_min) + max(0, close_min - 22*60)

            result['night_ratio'] = night_covered / night_min
            result['night_service'] = result['night_ratio'] > 0.5
            result['open_time'] = f"{open_h:02d}:{open_m:02d}"
            result['close_time'] = f"{close_h:02d}:{close_m:02d}"
        except:
            pass

    return result


# ============================================================
# 执行示例
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("大众点评/高德 POI 营业时间采集")
    print("="*70)

    # 方式1: 高德地图 API（推荐，免费）
    print("\n[方式1] 高德地图 Web API")
    print("-"*50)
    gaode = GaodeWebAPI(api_key=os.getenv('GAODE_API_KEY'))

    if gaode.api_key:
        # 采集各类设施
        categories = [
            '医院', '药店', '24小时药店',
            '超市', '便利店', '24小时便利店',
            '银行', 'ATM',
            '餐厅', '快餐', '小吃',
            '酒店', '宾馆',
            'KTV', '电影院', '健身房',
        ]

        output = f"{BASE}/data/poi_hours/gaode_nanshan_poi.csv"
        df = collect_night_service_poi(gaode, categories, output)

        # 解析营业时间
        if len(df) > 0:
            df['biz_ext_parse'] = df['biz_ext'].apply(parse_business_hours)
            print("\n夜间服务设施统计:")
            print(f"  24小时营业: {df['biz_ext_parse'].apply(lambda x: x['is_24h']).sum()}")
            print(f"  提供夜间服务: {df['biz_ext_parse'].apply(lambda x: x['night_service']).sum()}")
    else:
        print("""
[!] 请配置高德 API Key:
    1. 访问 https://lbs.amap.com/
    2. 注册账号并创建应用
    3. 获取 Web API Key
    4. 设置环境变量: set GAODE_API_KEY=your_key
        """)

    # 方式2: 美团开放平台（需企业资质）
    print("\n" + "="*70)
    print("[方式2] 美团开放平台 API（需企业资质）")
    print("-"*50)
    print("""
申请步骤:
1. 访问 https://open.meituan.com/
2. 使用企业资质注册
3. 创建应用并申请 POI 相关权限
4. 获取 app_id 和 app_secret
5. 设置环境变量:
   set MEITUAN_APP_ID=your_app_id
   set MEITUAN_APP_SECRET=your_app_secret

API 文档: https://open.meituan.com/docs/
    """)

print("\n*** P5 脚本结束 ***")
