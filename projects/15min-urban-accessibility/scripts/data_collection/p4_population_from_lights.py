# -*- coding: utf-8 -*-
"""
P4: 夜间灯光遥感数据估算人口
使用 NPP-VIIRS 夜间灯光数据估算南山区精细化人口分布

数据来源:
- NASA EOSDIS: https://eogdata.mines.edu/products/vnl/
- 国家对地观测科学数据中心: https://cms.casdc.cn/

方法:
1. 下载南山区范围的 NPP-VIIRS 夜间灯光影像
2. 与社区/小区边界进行分区统计
3. 建立灯光强度与人口的回归模型
4. 估算各社区精细化人口
"""

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box
import os
import sys
import io
import requests
from rasterio.mask import mask
from rasterio.features import geometry_mask
import rasterio

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = r"E:\xicha gis 智能定位\15分钟城市时间贫困研究"
os.makedirs(f"{BASE}/data/population", exist_ok=True)

# 南山区边界 (WGS84)
NS_BBOX = {
    'north': 22.65,
    'south': 22.45,
    'east': 114.05,
    'west': 113.85
}

print("="*70)
print("P4: 夜间灯光遥感数据估算人口")
print("="*70)

# ============================================================
# Step 1: 数据下载
# ============================================================
print("\n[Step 1] 数据下载")
print("-"*50)

# NPP-VIIRS 年度合成产品下载链接（需注册 NASA Earthdata）
# https://eogdata.mines.edu/products/vnl/#annual_v2
#
# 免费下载，无需 API Key：
# 1. 访问 https://eogdata.mines.edu/products/vnl/
# 2. 选择 Annual VNL V2
# 3. 选择年份（如 2023）
# 4. 下载 GeoTIFF 格式

VIIRS_URL_TEMPLATE = (
    "https://eogdata.mines.edu/products/vnl/"
    "v2/2023/Finalpro_VNL_v2_{year}_2023.tif"
)

def download_viirs_data(year=2023, save_dir=f"{BASE}/data/population"):
    """
    下载 NPP-VIIRS 夜间灯光年度合成数据

    参数:
        year: 年份 (2012-2023)
        save_dir: 保存目录
    返回:
        tif_path: GeoTIFF 文件路径
    """
    # 实际下载需要 NASA Earthdata 账号
    # 临时文件路径（假设已下载）
    tif_path = os.path.join(save_dir, f"VNL_v2_{year}.tif")

    if os.path.exists(tif_path):
        print(f"  [OK] 已存在: {tif_path}")
        return tif_path

    print(f"  [!] 请手动下载 NPP-VIIRS 数据:")
    print(f"      1. 访问: https://eogdata.mines.edu/products/vnl/")
    print(f"      2. 选择 Annual VNL v2.1")
    print(f"      3. 下载 {year} 年 GeoTIFF")
    print(f"      4. 保存到: {save_dir}")
    return None

# ============================================================
# Step 2: 灯光数据裁剪
# ============================================================
print("\n[Step 2] 灯光数据裁剪到南山区范围")
print("-"*50)

def clip_to_nanshan(viirs_tif, output_tif, bbox):
    """
    将 VIIRS 灯光数据裁剪到南山区范围
    """
    with rasterio.open(viirs_tif) as src:
        # 创建裁剪边界
        left, bottom = bbox['west'], bbox['south']
        right, top = bbox['east'], bbox['north']
        geom = box(left, bottom, right, top)

        # 裁剪
        out_image, out_transform = mask(src, [geom], crop=True)
        out_meta = src.meta.copy()

        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        with rasterio.open(output_tif, "w", **out_meta) as dst:
            dst.write(out_image)

    print(f"  [OK] 已保存: {output_tif}")
    return output_tif

# ============================================================
# Step 3: 人口估算模型
# ============================================================
print("\n[Step 3] 建立灯光-人口估算模型")
print("-"*50)

def estimate_population_from_lights(viirs_tif, communities_gdf, method='ratio'):
    """
    基于夜间灯光强度估算各社区人口

    参数:
        viirs_tif: VIIRS 灯光数据路径
        communities_gdf: 社区 GeoDataFrame
        method: 'ratio' (比值法) 或 'regression' (回归法)

    返回:
        communities_gdf: 包含 population_est 列的 GeoDataFrame
    """
    # 读取灯光数据
    with rasterio.open(viirs_tif) as src:
        viirs_data = src.read(1)
        viirs_transform = src.transform

    # 计算各社区的平均灯光强度
    avg_lights = []
    for idx, row in communities_gdf.iterrows():
        try:
            geom = row.geometry
            mask = geometry_mask([geom], out_shape=viirs_data.shape,
                                transform=viirs_transform)
            values = viirs_data[mask]
            avg_light = np.mean(values[values > 0]) if np.any(values > 0) else 0
            avg_lights.append(avg_light)
        except:
            avg_lights.append(0)

    communities_gdf['avg_light'] = avg_lights

    # 方法1: 比值法（需已知总人口）
    if method == 'ratio':
        # 南山区2023年常住人口约 160 万
        total_pop = 1600000
        light_sum = communities_gdf['avg_light'].sum()
        communities_gdf['population_est'] = (
            communities_gdf['avg_light'] / light_sum * total_pop
        ).astype(int)

    # 方法2: 回归法（需部分真实人口数据校准）
    elif method == 'regression':
        # 使用已知的部分小区人口进行线性回归校准
        # y = a * x + b, 其中 y=人口, x=灯光强度
        pass  # 需要部分真实数据

    print(f"  [OK] 人口估算完成")
    print(f"  估算人口总数: {communities_gdf['population_est'].sum():,}")
    print(f"  平均灯光强度: {communities_gdf['avg_light'].mean():.2f}")

    return communities_gdf


# ============================================================
# 执行流程
# ============================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("开始夜间灯光人口估算")
    print("="*70)

    # 步骤1: 下载数据
    viirs_tif = download_viirs_data(2023)

    if viirs_tif and os.path.exists(viirs_tif):
        # 步骤2: 裁剪
        clipped_tif = f"{BASE}/data/population/nanshan_viirs_2023.tif"
        clip_to_nanshan(viirs_tif, clipped_tif, NS_BBOX)

        # 步骤3: 加载社区边界
        communities = gpd.read_file(f"{BASE}/osm_data/nanshan_villages_with_building.geojson")

        # 步骤4: 估算人口
        communities = estimate_population_from_lights(clipped_tif, communities)

        # 步骤5: 保存结果
        output_path = f"{BASE}/osm_data/nanshan_communities_population.csv"
        communities.to_csv(output_path, index=False)
        print(f"\n[OK] 结果已保存: {output_path}")
    else:
        print("\n[!] 请先下载 VIIRS 数据")
        print("\n下载指南:")
        print("="*50)
        print("1. 访问 NASA EARTHDATA: https://eogdata.mines.edu/products/vnl/")
        print("2. 注册账号（免费）")
        print("3. 选择: Annual VNL v2.1 -> 2023")
        print("4. 下载 GeoTIFF 格式")
        print("5. 保存到:", f"{BASE}/data/population/")
        print("="*50)

print("\n*** P4 脚本结束 ***")
