# -*- coding: utf-8 -*-
"""
P5-Gaode: 使用高德 Web API 采集南山区的夜间服务 POI 数据

API 凭证:
- Web服务 Key: c2d6e6faba4fba3311618be75e07cdee
- 每日 2000 次, 总共 4000 次, 有效期至 2026-05-23
"""

import pandas as pd
import numpy as np
import os
import sys
import io
import time
import json
import requests
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.makedirs(f"{BASE}/data/gaode_poi", exist_ok=True)

# 高德 API 配置
GAODE_KEY = "c2d6e6faba4fba3311618be75e07cdee"
GAODE_BASE = "https://restapi.amap.com/v3"

# 南山区中心点和范围
NS_CENTER = "113.9308,22.5332"  # 南山区中心
NS_BOUND = {
    'south': 22.45, 'north': 22.65,
    'west': 113.85, 'east': 114.05
}

# 重点采集的设施类别（与夜间服务研究相关）
CATEGORIES = {
    # 医疗类 (高优先级 - 夜间关键)
    '医院': {'types': '090100', 'priority': 1},
    '诊所': {'types': '090200', 'priority': 1},
    '药店': {'types': '090101', 'priority': 1},
    '24小时药店': {'types': '090101', 'keyword': '24小时,24h,24小时', 'priority': 1},
    # 零售类
    '便利店': {'types': '100102', 'priority': 2},
    '24小时便利店': {'types': '100102', 'keyword': '24小时,24h,24', 'priority': 1},
    '超市': {'types': '100100', 'priority': 2},
    # 餐饮类
    '餐厅': {'types': '050100', 'priority': 2},
    '小吃快餐': {'types': '050300', 'priority': 2},
    '咖啡茶饮': {'types': '050500', 'priority': 3},
    # 金融类
    '银行': {'types': '150900', 'priority': 2},
    'ATM': {'types': '150904', 'priority': 2},
    # 交通类
    '地铁站': {'types': '150500', 'priority': 3},
    '公交站': {'types': '150700', 'priority': 3},
    # 住宿类
    '酒店': {'types': '100101', 'priority': 2},
    '宾馆': {'types': '100102', 'priority': 3},
    # 娱乐类
    'KTV': {'types': '080301', 'priority': 2},
    '电影院': {'types': '080101', 'priority': 2},
    '健身房': {'types': '080400', 'priority': 3},
    '网吧': {'types': '080401', 'priority': 3},
    # 公共设施
    '公共厕所': {'types': '180300', 'priority': 3},
}

# 统计调用量
CALL_STATS = {'success': 0, 'failed': 0, 'total': 0}
REMAINING_CALLS = 4000  # 总量限制

def search_poi(keywords, city='深圳', citylimit=True, offset=20, page=1, types=''):
    """搜索 POI"""
    global REMAINING_CALLS, CALL_STATS

    if REMAINING_CALLS <= 0:
        print("[STOP] API 调用量已用尽!")
        return None

    params = {
        'key': GAODE_KEY,
        'keywords': keywords,
        'city': city,
        'citylimit': 'true' if citylimit else 'false',
        'offset': offset,
        'page': page,
        'types': types,
        'output': 'json',
        'extensions': 'all',  # 获取详细信息
    }

    REMAINING_CALLS -= 1
    CALL_STATS['total'] += 1

    try:
        resp = requests.get(f"{GAODE_BASE}/place/text", params=params, timeout=15)
        data = resp.json()

        if data.get('status') == '1':
            CALL_STATS['success'] += 1
            pois = data.get('pois', [])
            count = int(data.get('count', 0))
            return pois, count
        else:
            CALL_STATS['failed'] += 1
            print(f"    [ERROR] {data.get('info', '未知错误')}")
            return None, 0
    except Exception as e:
        CALL_STATS['failed'] += 1
        print(f"    [EXCEPTION] {e}")
        return None, 0


def get_poi_detail(poi_id):
    """获取 POI 详情（含营业时间）"""
    global REMAINING_CALLS

    if REMAINING_CALLS <= 0:
        return None

    params = {
        'key': GAODE_KEY,
        'id': poi_id,
        'output': 'json',
    }

    REMAINING_CALLS -= 1
    CALL_STATS['total'] += 1

    try:
        resp = requests.get(f"{GAODE_BASE}/place/detail", params=params, timeout=15)
        data = resp.json()
        if data.get('status') == '1':
            CALL_STATS['success'] += 1
            return data
        return None
    except:
        CALL_STATS['failed'] += 1
        return None


def parse_business_hours(poi_record):
    """
    解析营业时间，判断是否提供夜间服务

    返回: dict {
        'night_service': bool,
        'is_24h': bool,
        'business_period': str,
        'night_ratio': float (0-1),
        'open_time': str,
        'close_time': str
    }
    """
    import re

    result = {
        'night_service': False,
        'is_24h': False,
        'business_period': '',
        'night_ratio': 0.0,
        'open_time': '',
        'close_time': '',
    }

    # 从字段提取营业时间
    # 高德返回的营业时间字段可能是: opentime, business_time, 营业时间
    hours_str = (
        poi_record.get('opentime') or
        poi_record.get('business_time') or
        poi_record.get('营业时间') or ''
    )

    result['business_period'] = str(hours_str)

    # 判断 24 小时
    if '24' in result['business_period'] or '24小时' in result['business_period']:
        result['is_24h'] = True
        result['night_service'] = True
        result['night_ratio'] = 1.0
        return result

    if not hours_str or hours_str in ['', 'null', 'None']:
        return result

    # 解析时间范围
    time_pattern = r'(\d{1,2}):(\d{2})'
    hours = re.findall(time_pattern, str(hours_str))

    if len(hours) >= 2:
        try:
            open_h, open_m = int(hours[0][0]), int(hours[0][1])
            close_h, close_m = int(hours[-1][0]), int(hours[-1][1])

            open_min = open_h * 60 + open_m
            close_min = close_h * 60 + close_m

            result['open_time'] = f"{open_h:02d}:{open_m:02d}"
            result['close_time'] = f"{close_h:02d}:{close_m:02d}"

            # 夜间时段: 22:00 - 06:00 (8小时)
            NIGHT_START = 22 * 60  # 1320 min
            NIGHT_END = 6 * 60    # 360 min
            NIGHT_DURATION = 8 * 60  # 480 min

            night_covered = 0
            if close_min > open_min:
                # 当天营业
                night_covered = max(0, close_min - max(open_min, NIGHT_START))
                night_covered += max(0, min(open_min, NIGHT_END) - 0)
            else:
                # 跨天营业 (e.g., 08:00 - 02:00)
                # 22:00-24:00
                night_covered = max(0, 24*60 - max(open_min, NIGHT_START))
                # 00:00-02:00
                night_covered += max(0, min(close_min, NIGHT_END) - 0)

            result['night_ratio'] = min(1.0, night_covered / NIGHT_DURATION)
            result['night_service'] = result['night_ratio'] > 0.5  # 超过50%夜间时段视为夜间服务
        except:
            pass

    return result


def collect_category(keyword, types='', max_pages=5, get_details=True):
    """采集单个类别的 POI"""
    all_pois = []

    for page in range(1, max_pages + 1):
        if REMAINING_CALLS <= 100:  # 保留100次余量
            print(f"    [WARN] 剩余调用量不足 ({REMAINING_CALLS}), 停止采集")
            break

        pois, total_count = search_poi(keyword, types=types, page=page)
        if not pois:
            break

        for poi in pois:
            # 解析夜间服务
            night_info = parse_business_hours(poi)

            record = {
                'name': poi.get('name', ''),
                'address': poi.get('address', ''),
                'location': poi.get('location', ''),
                'tel': poi.get('tel', ''),
                'type': poi.get('type', ''),
                'type_code': poi.get('typecode', ''),
                'keyword': keyword,
                'business_period': night_info['business_period'],
                'open_time': night_info['open_time'],
                'close_time': night_info['close_time'],
                'is_24h': night_info['is_24h'],
                'night_ratio': night_info['night_ratio'],
                'night_service': night_info['night_service'],
                'pcode': poi.get('pcode', ''),
                'citycode': poi.get('citycode', ''),
                'adcode': poi.get('adcode', ''),
                'gridcode': poi.get('gridcode', ''),
                'timestamp': datetime.now().isoformat(),
            }
            all_pois.append(record)

            # 获取详情（含更多信息）
            if get_details and REMAINING_CALLS > 100:
                poi_id = poi.get('id', '')
                if poi_id:
                    detail = get_poi_detail(poi_id)
                    if detail and 'detail' in detail:
                        d = detail['detail']
                        record.update({
                            'alias': d.get('alias', ''),
                            'tag': d.get('tag', ''),
                            'biz_type': d.get('biz_type', ''),
                            'ext_type': d.get('ext_type', ''),
                        })

        print(f"    第{page}页: {len(pois)} 条, 累计: {len(all_pois)}, 剩余: {REMAINING_CALLS}")
        time.sleep(0.15)  # 避免请求过快

    return all_pois


def main():
    global REMAINING_CALLS

    print("="*70)
    print("P5-Gaode: 高德 API 夜间服务 POI 采集")
    print("="*70)
    print(f"API Key: {GAODE_KEY[:10]}...{GAODE_KEY[-4:]}")
    print(f"剩余调用量: {REMAINING_CALLS}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    all_records = []

    # 按优先级排序，先采集高优先级的
    sorted_cats = sorted(CATEGORIES.items(), key=lambda x: x[1]['priority'])

    for cat_name, cat_info in sorted_cats:
        if REMAINING_CALLS <= 50:
            print(f"\n[STOP] API 调用量即将耗尽, 停止采集")
            break

        print(f"\n[{cat_info['priority']}] 采集: {cat_name}")
        print("-"*50)

        keyword = cat_info.get('keyword', cat_name)
        types = cat_info.get('types', '')

        # 根据优先级决定采集页数
        max_pages = 5 if cat_info['priority'] <= 1 else 3

        records = collect_category(keyword, types=types, max_pages=max_pages)
        all_records.extend(records)

        print(f"    小计: {len(records)} 条, 总计: {len(all_records)}, 剩余: {REMAINING_CALLS}")
        time.sleep(0.5)

    # 保存结果
    if all_records:
        df = pd.DataFrame(all_records)
        # 去重
        df = df.drop_duplicates(subset=['name', 'location'], keep='first')

        output_path = f"{BASE}/data/gaode_poi/nanshan_night_service_poi.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n[OK] 已保存 {len(df)} 条 POI 到: {output_path}")

        # 统计夜间服务
        print("\n" + "="*70)
        print("夜间服务统计")
        print("="*70)
        print(f"总 POI: {len(df)}")
        print(f"24小时营业: {df['is_24h'].sum()}")
        print(f"夜间服务: {df['night_service'].sum()}")
        print(f"夜间比例均值: {df['night_ratio'].mean():.2%}")

        print("\n按类别统计:")
        for cat in df['keyword'].unique():
            sub = df[df['keyword'] == cat]
            n_night = sub['night_service'].sum()
            print(f"  {cat}: {len(sub)} 条, 夜间服务 {n_night} ({100*n_night/len(sub):.1f}%)")
    else:
        print("\n[ERROR] 未采集到任何数据")

    # 调用统计
    print("\n" + "="*70)
    print("API 调用统计")
    print("="*70)
    print(f"总调用: {CALL_STATS['total']}")
    print(f"成功: {CALL_STATS['success']}")
    print(f"失败: {CALL_STATS['failed']}")
    print(f"剩余: {REMAINING_CALLS}")

    print("\n*** P5-Gaode 完成 ***")


if __name__ == "__main__":
    main()
