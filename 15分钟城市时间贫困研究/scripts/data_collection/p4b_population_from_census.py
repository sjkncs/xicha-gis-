# -*- coding: utf-8 -*-
"""
P4b: 深圳市统计局分区人口数据获取

数据来源:
1. 深圳统计年鉴 (2024/2025)
   - 深圳市统计局网站: http://tjj.sz.gov.cn/
   - 年鉴分享站: https://www.tjnj.net/

2. 分区数据
   - 各区年末常住人口 (2018-2024)
   - 分区国土调查面积及人口密度

3. 街道/社区级数据
   - 需联系深圳市统计局申请
   - 电话: 0755-88120163
"""

import pandas as pd
import numpy as np
import os
import sys
import io
import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.makedirs(f"{BASE}/data/population", exist_ok=True)

print("="*70)
print("P4b: 深圳市统计局分区人口数据获取指南")
print("="*70)

# ============================================================
# 方法1: 从统计年鉴获取分区人口数据
# ============================================================
print("\n[方法1] 深圳统计年鉴 - 分区人口数据")
print("-"*50)

# 2024年南山区人口（示例数据，需从年鉴获取真实数据）
# 来源: 2025年深圳统计年鉴
SHENZHEN_POPULATION_2024 = {
    '南山区': 1600000,      # 需核实
    '福田区': 1600000,      # 需核实
    '罗湖区': 1000000,      # 需核实
    '宝安区': 4500000,      # 需核实
    '龙岗区': 4000000,      # 需核实
    '龙华区': 3000000,      # 需核实
    '坪山区': 1000000,      # 需核实
    '光明区': 1100000,      # 需核实
    '盐田区': 500000,       # 需核实
    '大鹏新区': 400000,     # 需核实
}

def load_shenzhen_census_population(year=2024):
    """
    从本地年鉴文件加载深圳分区人口数据

    参数:
        year: 年份

    返回:
        DataFrame: 分区人口数据
    """
    # 检查是否有本地年鉴数据
    census_path = f"{BASE}/data/population/shenzhen_census_{year}.csv"

    if os.path.exists(census_path):
        print(f"  [OK] 从本地加载: {census_path}")
        return pd.read_csv(census_path)

    # 返回最新可用数据（需手动更新）
    print("  [!] 请下载最新深圳统计年鉴并保存到:")
    print(f"      {census_path}")
    print("  [方式A] 在线获取:")
    print("      1. 访问: https://www.tjnj.net/navipage-n3026031404000101.html")
    print("      2. 下载 2025年深圳统计年鉴")
    print("      3. 提取 '1-2 分区人口及人口密度' 表")
    print("  [方式B] 联系统计局:")
    print("      电话: 0755-88120163")

    # 返回占位数据
    df = pd.DataFrame([
        {'district': k, 'population': v, 'year': year}
        for k, v in SHENZHEN_POPULATION_2024.items()
    ])
    df['data_source'] = 'placeholder_需更新'
    return df


# ============================================================
# 方法2: 街道级人口估算（基于面积比例分配）
# ============================================================
print("\n[方法2] 街道级人口估算")
print("-"*50)

def estimate_street_population(district_pop, streets_df, method='area_ratio'):
    """
    基于面积比例估算各街道人口

    参数:
        district_pop: 区级总人口
        streets_df: 街道边界数据（GeoDataFrame）
        method: 'area_ratio' (面积比) 或 'density_ratio' (密度比)

    返回:
        DataFrame: 各街道人口估算
    """
    if 'area_km2' not in streets_df.columns:
        # 计算面积（需投影坐标）
        streets_df['area_km2'] = streets_df.geometry.area / 1e6  # 假设 EPSG:4326

    total_area = streets_df['area_km2'].sum()
    streets_df['pop_est'] = (streets_df['area_km2'] / total_area * district_pop).astype(int)
    streets_df['pop_density'] = streets_df['pop_est'] / streets_df['area_km2']

    print(f"  区总人口: {district_pop:,}")
    print(f"  街道数: {len(streets_df)}")
    print(f"  估算人口密度: {streets_df['pop_density'].mean():.0f} 人/km²")

    return streets_df


# ============================================================
# 方法3: 基于小区面积的精细化人口估算
# ============================================================
print("\n[方法3] 小区级人口精细化估算")
print("-"*50)

def estimate_community_population_v2(communities_df, district_pop=1600000):
    """
    基于建筑面积估算各小区人口

    参数:
        communities_df: 小区数据（含 area_m2 列）
        district_pop: 南山区总人口

    返回:
        DataFrame: 含 population_est 列的小区数据
    """
    # 方法: 假设人口与建筑面积成正比
    total_area = communities_df['area_m2'].sum()
    communities_df['population_est'] = (
        communities_df['area_m2'] / total_area * district_pop
    ).astype(int)

    # 附加: 基于小区类型调整
    TYPE_ADJUSTMENT = {
        'urban_village': 1.5,      # 城中村人口密度更高
        'affordable_housing': 1.2,   # 保障房密度较高
        'commodity_housing': 1.0,   # 商品房基准
        'high_end': 0.8,            # 高端社区密度较低
    }

    communities_df['pop_adjustment'] = communities_df['community_type'].map(
        TYPE_ADJUSTMENT).fillna(1.0)
    communities_df['population_est'] = (
        communities_df['population_est'] * communities_df['pop_adjustment']
    ).astype(int)

    # 归一化到区总人口
    pop_sum = communities_df['population_est'].sum()
    communities_df['population_est'] = (
        communities_df['population_est'] / pop_sum * district_pop
    ).astype(int)

    print(f"  小区数: {len(communities_df)}")
    print(f"  估算总人口: {communities_df['population_est'].sum():,}")
    print(f"  平均小区人口: {communities_df['population_est'].mean():.0f}")

    return communities_df


# ============================================================
# 执行示例
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("分区人口数据获取")
    print("="*70)

    # 方法1: 加载年鉴数据
    census_df = load_shenzhen_census_population(2024)
    print("\n深圳分区人口 (示例):")
    print(census_df.to_string(index=False))

    print("\n" + "="*70)
    print("下一步操作")
    print("="*70)
    print("""
1. 下载 2025年深圳统计年鉴:
   https://www.tjnj.net/navipage-n3026031404000101.html

2. 提取分区人口数据并保存为:
   data/population/shenzhen_census_2024.csv

3. 联系深圳市统计局获取街道级数据:
   电话: 0755-88120163
   网站: http://tjj.sz.gov.cn/

4. 运行 p4_population_from_lights.py 进行灯光遥感估算
    """)

print("\n*** P4b 脚本结束 ***")
