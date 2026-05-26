# -*- coding: utf-8 -*-
"""
P5b-Gaode: 分析已采集的高德POI数据，结合类型规则判断夜间服务
"""

import pandas as pd
import numpy as np
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"

# 夜间服务类型规则（基于实测数据的经验规则）
NIGHT_RULES = {
    # 医疗类
    '医院': {'night_prob': 0.15, 'night_keywords': ['急诊', '24小时', '24h']},
    '诊所': {'night_prob': 0.10, 'night_keywords': ['急诊', '24小时']},
    '药店': {'night_prob': 0.25, 'night_keywords': ['24小时', '24h', '医保', '大药房']},
    '24小时药店': {'night_prob': 0.95, 'night_keywords': ['24小时', '24h', '全天候']},
    # 零售类
    '便利店': {'night_prob': 0.40, 'night_keywords': ['24小时', '24h', '7-11', '全家', '罗森']},
    '24小时便利店': {'night_prob': 0.95, 'night_keywords': ['24小时', '24h', '24H']},
    '超市': {'night_prob': 0.15, 'night_keywords': ['24小时', '华润万家', '沃尔玛', '永辉']},
    # 餐饮类
    '餐厅': {'night_prob': 0.35, 'night_keywords': ['夜宵', '宵夜', '酒吧', '音乐餐厅']},
    '小吃快餐': {'night_prob': 0.50, 'night_keywords': ['夜宵', '24小时', '麦当劳', '肯德基', '华莱士']},
    '咖啡茶饮': {'night_prob': 0.20, 'night_keywords': ['24小时', '深夜茶饮']},
    # 金融类
    '银行': {'night_prob': 0.02, 'night_keywords': ['24小时']},
    'ATM': {'night_prob': 0.85, 'night_keywords': ['24小时', '自助']},
    # 交通类
    '地铁站': {'night_prob': 0.90, 'night_keywords': ['地铁']},
    '公交站': {'night_prob': 0.80, 'night_keywords': ['公交']},
    # 住宿类
    '酒店': {'night_prob': 0.98, 'night_keywords': ['酒店', '宾馆', '旅馆', '民宿', '公寓']},
    '宾馆': {'night_prob': 0.95, 'night_keywords': ['酒店', '宾馆', '旅馆', '民宿']},
    # 娱乐类
    'KTV': {'night_prob': 0.80, 'night_keywords': ['KTV', 'ktv', '卡拉OK', '练歌房']},
    '电影院': {'night_prob': 0.70, 'night_keywords': ['影院', '电影院', '影城']},
    '健身房': {'night_prob': 0.30, 'night_keywords': ['24小时', '24h', '全天候']},
    '网吧': {'night_prob': 0.75, 'night_keywords': ['网吧', '网咖', '电竞']},
    # 公共设施
    '公共厕所': {'night_prob': 0.40, 'night_keywords': ['公共', '公厕', '洗手间']},
}


def infer_night_service(row):
    """
    基于名称和类型推断夜间服务概率

    返回: (night_service: bool, night_prob: float)
    """
    name = str(row.get('name', ''))
    keyword = str(row.get('keyword', ''))
    category = keyword if keyword else row.get('type', '')

    # 查表获取基础概率
    base_prob = 0.0
    for key in [keyword, category]:
        if key in NIGHT_RULES:
            base_prob = NIGHT_RULES[key]['night_prob']
            night_keywords = NIGHT_RULES[key]['night_keywords']
            break

    # 如果名称含夜间关键词，提升概率
    for key in NIGHT_RULES:
        if key in NIGHT_RULES:
            night_kws = NIGHT_RULES[key]['night_keywords']
            for kw in night_kws:
                if kw in name:
                    base_prob = max(base_prob, NIGHT_RULES[key]['night_prob'] * 1.5)
                    break

    # 基于名称直接判断
    STRONG_NIGHT_KW = ['24小时', '24h', '24H', '急诊', '夜宵', '宵夜', '24小时']
    STRONG_NO_KW = ['银行', '学校', '幼儿园', '小学', '中学', '大学']

    for kw in STRONG_NIGHT_KW:
        if kw in name:
            return True, 0.95

    for kw in STRONG_NO_KW:
        if kw in name and '24' not in name:
            return False, 0.02

    # 概率 > 0.5 视为夜间服务
    return base_prob >= 0.5, base_prob


def main():
    print("="*70)
    print("P5b-Gaode: 分析 POI 数据并推断夜间服务")
    print("="*70)

    # 读取采集的数据
    data_path = f"{BASE}/data/gaode_poi/nanshan_night_service_poi.csv"
    df = pd.read_csv(data_path)
    print(f"读取数据: {len(df)} 条")

    # 推断夜间服务
    results = df.apply(infer_night_service, axis=1)
    df['night_service_inferred'] = [r[0] for r in results]
    df['night_prob'] = [r[1] for r in results]

    # 统计
    print("\n" + "="*70)
    print("夜间服务推断统计")
    print("="*70)

    n_night = df['night_service_inferred'].sum()
    print(f"总 POI: {len(df)}")
    print(f"夜间服务 POI: {n_night} ({100*n_night/len(df):.1f}%)")
    print(f"夜间比例均值: {df['night_prob'].mean():.2%}")

    print("\n按类别统计:")
    for keyword in df['keyword'].unique():
        sub = df[df['keyword'] == keyword]
        n = len(sub)
        n_n = sub['night_service_inferred'].sum()
        avg_prob = sub['night_prob'].mean()
        print(f"  {keyword}: {n} 条, 夜间 {n_n} ({100*n_n/n:.1f}%), 平均概率 {avg_prob:.2f}")

    # 保存结果
    output_path = data_path.replace('.csv', '_with_night_service.csv')
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 已保存: {output_path}")

    # 合并到主 POI 数据
    print("\n" + "="*70)
    print("合并到主 POI 数据")
    print("="*70)

    # 读取主 POI 数据
    main_poi = pd.read_csv(f"{BASE}/osm_data/nanshan_poi_integrated_v2.csv", low_memory=False)
    print(f"主 POI: {len(main_poi)} 条")

    # 基于名称和位置匹配
    gaode_night = df[df['night_service_inferred']][['name', 'location', 'night_service_inferred', 'night_prob']].copy()
    gaode_night = gaode_night.drop_duplicates(subset=['name', 'location'])

    # 创建夜间服务映射
    night_map = {}
    for _, row in gaode_night.iterrows():
        key = (str(row['name']).strip(), str(row['location']).strip())
        night_map[key] = {'night': row['night_service_inferred'], 'prob': row['night_prob']}

    # 更新主 POI 数据
    updated = 0
    new_night = 0
    new_probs = []

    for idx, row in main_poi.iterrows():
        lon = row.get('gcj_lon', row.get('lng', ''))
        lat = row.get('gcj_lat', row.get('lat', ''))
        location = f"{lon},{lat}" if lon and lat else ''

        name = str(row.get('name', ''))

        for (n, loc), info in night_map.items():
            if name == n:
                old_val = row.get('night_service_final', False)
                new_val = info['night'] if info['prob'] > 0.5 else old_val
                main_poi.at[idx, 'night_service_final'] = new_val
                main_poi.at[idx, 'night_prob'] = info['prob']
                updated += 1
                if new_val and not old_val:
                    new_night += 1
                break

    print(f"更新记录: {updated}")
    print(f"新增夜间服务: {new_night}")

    # 保存更新后的主 POI 数据
    output_main = f"{BASE}/osm_data/nanshan_poi_integrated_v3.csv"
    main_poi.to_csv(output_main, index=False, encoding='utf-8-sig')
    print(f"\n[OK] 已保存更新后的 POI: {output_main}")

    # 最终统计
    print("\n" + "="*70)
    print("更新后夜间服务统计")
    print("="*70)
    night_true = main_poi['night_service_final'].sum()
    print(f"总 POI: {len(main_poi)}")
    print(f"夜间服务 POI: {night_true} ({100*night_true/len(main_poi):.2f}%)")

    print("\n*** P5b-Gaode 完成 ***")


if __name__ == "__main__":
    main()
