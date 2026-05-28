# -*- coding: utf-8 -*-
"""
采样点准备脚本 - 南山区分层采样
从现有 CSV 提取采样点，按道路类型分层采样，
确保覆盖不同城市形态（Open/Other, Low-Rise, Mid-Rise, High-Rise）
API 配额 500次，需控制在500以内
"""

import os
import sys
import json
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd


BASE_DIR = r'e:\xicha gis 智能定位\projects\15min-urban-accessibility'
SAMPLES_DIR = os.path.join(BASE_DIR, 'data', 'dl_pipeline', 'samples')
os.makedirs(SAMPLES_DIR, exist_ok=True)


# 现有样本 CSV（可用）
SAMPLE_CSV_OPTIONS = [
    os.path.join(BASE_DIR, 'data', 'streetview', 'integrated_collection', 'samples', 'sample_points_n201.csv'),
]

# 备用：手动指定坐标（南山区代表性位置）
MANUAL_SAMPLES = [
    # (lng, lat, road_fclass, road_name, urban_form, notes)
    (113.9412, 22.5308, 'residential', '科技园南区', 'High-Rise', '深圳大学城/科技园核心'),
    (113.9290, 22.5220, 'primary', '南海大道', 'Mid-Rise', '商业主干道'),
    (113.9380, 22.5430, 'tertiary', '科技中三路', 'Mid-Rise', '科技园内部道路'),
    (113.9500, 22.5180, 'trunk', '滨海大道', 'Open/Other', '滨海/快速路'),
    (113.9250, 22.5150, 'tertiary', '登良路', 'Low-Rise', '居住区道路'),
    (113.9450, 22.5350, 'residential', '海德三道', 'High-Rise', '后海中心区'),
    (113.9350, 22.5100, 'primary', '东滨路', 'Mid-Rise', '城中村过渡区'),
    (113.9550, 22.5270, 'cycleway', '深圳湾体育中心', 'Open/Other', '骑行/步行道'),
    (113.9200, 22.5450, 'service', '南光社区', 'Low-Rise', '老旧住宅区'),
    (113.9600, 22.5380, 'trunk', '沙河西路', 'High-Rise', '华侨城/豪宅区'),
    (113.9300, 22.5300, 'tertiary', '文心五路', 'Mid-Rise', '海岸城商圈'),
    (113.9100, 22.4920, 'tertiary', '水湾直街', 'Low-Rise', '海上世界/旧工业区'),
    (113.9700, 22.5600, 'tertiary', '龙井路', 'Open/Other', '塘朗山入口'),
    (113.9100, 22.5100, 'residential', '桂庙新村', 'Low-Rise', '城中村'),
    (113.9500, 22.5100, 'service', '前海深港合作区', 'High-Rise', '前海新区'),
]


def load_existing_samples():
    """从现有 CSV 加载样本点"""
    all_points = []
    for csv_path in SAMPLE_CSV_OPTIONS:
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path)
                print(f'  从 {os.path.basename(csv_path)} 加载 {len(df)} 个点')
                all_points.append(df)
            except Exception as e:
                print(f'  加载失败 {csv_path}: {e}')

    if all_points:
        combined = pd.concat(all_points, ignore_index=True)
        combined = combined.drop_duplicates(subset=['lng', 'lat'])
        return combined
    return pd.DataFrame()


def stratified_sample(df: pd.DataFrame, max_count: int, random_seed: int = 42) -> pd.DataFrame:
    """
    分层采样：按 urban_form 和 road_fclass 分层

    urban_form 分层:
    - High-Rise: 高层建筑区
    - Mid-Rise: 中层建筑区
    - Low-Rise: 低层建筑区（城中村/老旧）
    - Open/Other: 开放空间/其他

    目标: 每个城市形态至少有一定代表性
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    if len(df) <= max_count:
        print(f'  样本数 {len(df)} <= 限制 {max_count}，全部保留')
        return df.copy()

    # 分层
    urban_forms = df['urban_form'].fillna('Open/Other').unique()
    form_counts = df['urban_form'].fillna('Open/Other').value_counts()

    # 计算各层目标采样数（按比例分配，最少2个）
    n_forms = len(urban_forms)
    base_count = max_count // n_forms
    remainder = max_count % n_forms

    sampled_dfs = []
    form_list = sorted(urban_forms)

    for i, form in enumerate(form_list):
        # 多出来的配额分配给主要类别
        extra = 1 if i < remainder else 0
        target_n = min(base_count + extra, len(df[df['urban_form'].fillna('Open/Other') == form]))
        group = df[df['urban_form'].fillna('Open/Other') == form].copy()

        if target_n >= len(group):
            sampled_dfs.append(group)
        else:
            sampled_dfs.append(group.sample(n=target_n, random_state=random_seed))

    result = pd.concat(sampled_dfs, ignore_index=True)

    # 如果还不够，随机补充
    if len(result) < max_count:
        current_ids = set(zip(result['lng'], result['lat']))
        remaining = df[~df.apply(lambda r: (r['lng'], r['lat']) in current_ids, axis=1)]
        need = max_count - len(result)
        if len(remaining) > 0 and need > 0:
            extra = remaining.sample(n=min(need, len(remaining)), random_state=random_seed)
            result = pd.concat([result, extra], ignore_index=True)

    return result.head(max_count)


def add_manual_samples(existing_df: pd.DataFrame, manual_samples: list) -> pd.DataFrame:
    """合并手动指定的代表性样本"""
    if manual_samples:
        manual_df = pd.DataFrame(manual_samples, columns=[
            'lng', 'lat', 'road_fclass', 'road_name', 'urban_form', 'notes'
        ])
        manual_df['lng'] = pd.to_numeric(manual_df['lng'], errors='coerce')
        manual_df['lat'] = pd.to_numeric(manual_df['lat'], errors='coerce')
        manual_df = manual_df.dropna(subset=['lng', 'lat'])

        if len(existing_df) > 0:
            # 合并，优先保留手动样本的位置信息
            existing_ids = set(zip(existing_df['lng'], existing_df['lat']))
            new_manual = manual_df[~manual_df.apply(
                lambda r: (r['lng'], r['lat']) in existing_ids, axis=1
            )]
            result = pd.concat([new_manual, existing_df], ignore_index=True)
            print(f'  合并手动样本 {len(new_manual)} + 现有 {len(existing_df)} = {len(result)} 个')
            return result
        else:
            print(f'  仅使用 {len(manual_df)} 个手动样本')
            return manual_df
    return existing_df


def generate_sample_id(row: pd.Series, idx: int) -> str:
    """从坐标生成唯一ID"""
    coord_str = f"{row['lng']:.6f},{row['lat']:.6f}"
    hash_part = hashlib.md5(coord_str.encode()).hexdigest()[:6].upper()
    form_part = str(row.get('urban_form', 'OTHER'))[:3].upper()
    return f"SMP{idx:04d}_{form_part}_{hash_part}"


def prepare_samples(
    max_count: int = 300,
    use_manual: bool = True,
    output_csv: str = None,
    output_json: str = None,
) -> pd.DataFrame:
    """
    准备采样点

    参数:
        max_count: 最大采样点数（API配额500，留余量用于备用）
        use_manual: 是否包含手动指定的高代表性样本
        output_csv: 输出CSV路径
        output_json: 输出JSON路径

    返回:
        采样点 DataFrame
    """
    print('=' * 60)
    print('采样点准备')
    print('=' * 60)
    print(f'  最大采样数: {max_count}')
    print(f'  配额留余量: 预留50次（500总调用 - 300采样 = 200备用）')
    print()

    # Step 1: 加载现有样本
    print('[1] 加载现有样本点...')
    existing_df = load_existing_samples()

    # Step 2: 添加手动样本
    print('\n[2] 添加代表性样本...')
    if use_manual:
        combined_df = add_manual_samples(existing_df, MANUAL_SAMPLES)
    else:
        combined_df = existing_df

    if len(combined_df) == 0:
        print('  [WARN] 无现有样本，使用纯手动样本')
        combined_df = pd.DataFrame(MANUAL_SAMPLES, columns=[
            'lng', 'lat', 'road_fclass', 'road_name', 'urban_form', 'notes'
        ])

    # Step 3: 分层采样
    print(f'\n[3] 分层采样 (目标: {max_count} 点)...')
    sampled_df = stratified_sample(combined_df, max_count, random_seed=42)
    sampled_df = sampled_df.reset_index(drop=True)

    # 统计
    print(f'\n  采样后总数: {len(sampled_df)}')
    print(f'  城市形态分布:')
    form_counts = sampled_df['urban_form'].fillna('Open/Other').value_counts()
    for form, cnt in form_counts.items():
        print(f'    {form}: {cnt}')

    # Step 4: 生成唯一ID
    print('\n[4] 生成采样点ID...')
    sampled_df['sample_id'] = [generate_sample_id(row, i) for i, row in sampled_df.iterrows()]

    # Step 5: 添加元信息
    sampled_df['coord_hash'] = sampled_df.apply(
        lambda r: hashlib.md5(f"{r['lng']:.6f},{r['lat']:.6f}".encode()).hexdigest()[:8], axis=1
    )
    sampled_df['wgs84_lng'] = sampled_df['lng']
    sampled_df['wgs84_lat'] = sampled_df['lat']

    # Step 6: 整理列
    output_cols = [
        'sample_id', 'lng', 'lat', 'wgs84_lng', 'wgs84_lat',
        'road_fclass', 'road_name', 'urban_form',
        'edge_id', 'dist_from_start', 'edge_total_m',
        'bld_density_100m', 'avg_floors_100m',
        'village_nearby_cnt', 'highend_nearby_cnt',
        'coord_hash',
    ]
    existing_cols = [c for c in output_cols if c in sampled_df.columns]
    sampled_df = sampled_df[existing_cols]

    # 输出
    if output_csv:
        sampled_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f'\n[OK] CSV已保存: {output_csv}')

    if output_json:
        records = sampled_df.to_dict(orient='records')
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f'[OK] JSON已保存: {output_json}')

    print(f'\n统计摘要:')
    print(f'  总采样点: {len(sampled_df)}')
    print(f'  API配额消耗估算: {len(sampled_df)} 次静态地图调用')
    print(f'  备用余量: {500 - len(sampled_df)} 次')

    return sampled_df


def main():
    parser = argparse.ArgumentParser(description='准备采样点列表')
    parser.add_argument('--max', type=int, default=300,
                        help='最大采样数 (默认300，留200备用)')
    parser.add_argument('--no-manual', action='store_true',
                        help='不使用手动样本')
    parser.add_argument('--output-dir', default=SAMPLES_DIR,
                        help='输出目录')
    args = parser.parse_args()

    output_csv = os.path.join(args.output_dir, 'dl_sample_points.csv')
    output_json = os.path.join(args.output_dir, 'dl_sample_points.json')

    df = prepare_samples(
        max_count=args.max,
        use_manual=not args.no_manual,
        output_csv=output_csv,
        output_json=output_json,
    )

    print('\n' + '=' * 60)
    print('采样点准备完成')
    print('=' * 60)


if __name__ == '__main__':
    main()
