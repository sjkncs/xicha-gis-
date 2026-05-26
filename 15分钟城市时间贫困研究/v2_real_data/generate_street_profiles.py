，wowo# -*- coding: utf-8 -*-
"""
=============================================================================
Street Cross-Section Profile Generator (街道剖面图生成器)
=============================================================================

功能: 基于楼栋数据 + OSM路网，还原街道剖面图
- 横向: 道路 + 建筑名称 + 宽度 + 间距
- 纵向: 建筑高度(层数)
- 生成 ~400 张剖面图

依赖:
- building_data/南山区-房屋楼栋基础数据_2920004003598.csv
- osm_data/nanshan_network_nodes.csv
- osm_data/nanshan_poi_integrated_v3_wgs84.csv

=============================================================================
"""

import os
import sys
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
from scipy.cluster.hierarchy import fclusterdata
import re
from tqdm import tqdm

# ============================================================================
# 路径配置
# ============================================================================

BASE_DIR = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
BUILDING_CSV = os.path.join(BASE_DIR, 'building_data', '南山区-房屋楼栋基础数据_2920004003598.csv')
POI_CSV = os.path.join(BASE_DIR, 'osm_data', 'nanshan_poi_integrated_v3_wgs84.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'v2_real_data', 'street_profiles')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# 使用用途分类映射
# ============================================================================

USAGE_TYPE_MAP = {
    1: 'Residential',      # 住宅
    2: 'Residential',      # 住宅
    3: 'Mixed Residential', # 商住混合
    4: 'Commercial',       # 商业/办公
    5: 'Industrial',       # 工业
    6: 'Infrastructure',   # 基础设施
    7: 'Other',            # 其他
    8: 'Public',          # 公共设施
    0: 'Unknown',
}

USAGE_COLORS = {
    'Residential': '#3498db',       # 蓝色
    'Mixed Residential': '#9b59b6', # 紫色
    'Commercial': '#e74c3c',       # 红色
    'Industrial': '#95a5a6',        # 灰色
    'Infrastructure': '#f39c12',     # 橙色
    'Public': '#1abc9c',           # 青色
    'Other': '#7f8c8d',
    'Unknown': '#bdc3c7',
}

# ============================================================================
# 1. 数据加载与预处理
# ============================================================================

def load_building_data():
    """加载楼栋数据"""
    print("[1] 加载楼栋数据...")
    df = pd.read_csv(BUILDING_CSV, dtype=str, keep_default_na=False)
    
    # 解析坐标 (高德坐标 GCJ-02)
    df['gcj_lng'] = pd.to_numeric(df['中心坐标'], errors='coerce')
    df['gcj_lat'] = pd.to_numeric(df['中心点坐标'], errors='coerce')
    df['usage_type'] = pd.to_numeric(df['使用用途'], errors='coerce').fillna(0).astype(int)
    df['floor_count'] = pd.to_numeric(df['总层数'], errors='coerce').fillna(0).astype(int)
    df['building_name'] = df['名称'].str.strip()
    df['address'] = df['常用地址'].str.strip()
    
    # 过滤无效数据
    df = df.dropna(subset=['gcj_lng', 'gcj_lat'])
    df = df[df['floor_count'] > 0]
    
    # 转换为 WGS84 (简化处理)
    df['lng'] = df['gcj_lng']  # 后续需要转换，这里先简化
    df['lat'] = df['gcj_lat']
    
    # 添加用途分类
    df['usage_category'] = df['usage_type'].map(
        lambda x: USAGE_TYPE_MAP.get(x, 'Unknown')
    )
    
    print(f"  有效楼栋: {len(df)} 条")
    print(f"  层数范围: {df['floor_count'].min()} - {df['floor_count'].max()}")
    
    return df


def gcj02_to_wgs84(lng, lat):
    """GCJ-02 转 WGS84 (简化转换)"""
    a = 6378245.0
    ee = 0.00669342162296594323
    
    def transform(lat, lng):
        dlat = transform_lat(lng - 105.0, lat - 35.0)
        dlng = transform_lng(lng - 105.0, lat - 35.0)
        radlat = lat / 180.0 * np.pi
        magic = np.sin(radlat)
        magic = 1 - ee * magic * magic
        sqrtmagic = np.sqrt(magic)
        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * np.pi)
        dlng = (dlng * 180.0) / (a / sqrtmagic * np.cos(radlat) * np.pi)
        return dlat, dlng
    
    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * np.sqrt(abs(x))
        ret += (20.0 * np.sin(6.0 * x * np.pi) + 20.0 * np.sin(2.0 * x * np.pi)) * 2.0 / 3.0
        ret += (20.0 * np.sin(y * np.pi) + 40.0 * np.sin(y / 3.0 * np.pi)) * 2.0 / 3.0
        ret += (160.0 * np.sin(y / 12.0 * np.pi) + 320.0 * np.sin(y * np.pi / 30.0)) * 2.0 / 3.0
        return ret
    
    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * np.sqrt(abs(x))
        ret += (20.0 * np.sin(6.0 * x * np.pi) + 20.0 * np.sin(2.0 * x * np.pi)) * 2.0 / 3.0
        ret += (20.0 * np.sin(x * np.pi) + 40.0 * np.sin(x / 3.0 * np.pi)) * 2.0 / 3.0
        ret += (150.0 * np.sin(x / 12.0 * np.pi) + 300.0 * np.sin(x / 30.0 * np.pi)) * 2.0 / 3.0
        return ret
    
    dlat, dlng = transform(lat - 0, lng - 0)
    return lng - dlng, lat - dlat


# ============================================================================
# 2. 街道/道路聚类
# ============================================================================

def extract_road_name(address):
    """从地址中提取道路名称"""
    # 常见道路后缀
    road_patterns = [
        r'([\u4e00-\u9fa5]+大道)',
        r'([\u4e00-\u9fa5]+路)',
        r'([\u4e00-\u9fa5]+街)',
        r'([\u4e00-\u9fa5]+巷)',
        r'([\u4e00-\u9fa5]+道)',
        r'([\u4e00-\u9fa5]+路\b)',
    ]
    
    for pattern in road_patterns:
        match = re.search(pattern, address)
        if match:
            return match.group(1)
    
    return None


def cluster_buildings_by_road(df: pd.DataFrame, cluster_radius_deg: float = 0.003):
    """
    基于空间聚类将建筑分组到不同街道。
    同一街道的建筑在空间上相邻（纬度方向距离 < cluster_radius_deg）
    """
    print("[2] 按街道聚类建筑...")

    # 按纬度分块 (同一街道的建筑纬度相近)
    lat_bins = np.linspace(df['lat'].min() - 0.001, df['lat'].max() + 0.001, 100)
    df['lat_bin'] = pd.cut(df['lat'], bins=lat_bins, labels=range(len(lat_bins)-1))
    
    # 从地址提取道路名称
    df['road_name'] = df['address'].apply(extract_road_name)
    
    # 聚类策略:
    # 1. 先按道路名称分组
    # 2. 同一道路名称内，按纬度和经度排序
    # 3. 相邻建筑按距离分配到不同剖面
    
    streets = []
    
    # 按道路名称分组
    for road, group in df.groupby('road_name', dropna=False):
        if road is None or pd.isna(road):
            # 无道路名称的，按空间聚类
            group = cluster_nameless(group, cluster_radius_deg)
        
        streets.extend(group)
    
    if not streets:
        # 如果没有道路信息，按纬度分块
        streets = cluster_by_latitude(df, cluster_radius_deg)
    
    return streets


def cluster_nameless(group, radius):
    """聚类无道路名称的建筑"""
    if len(group) <= 3:
        return [group.assign(profile_id=i) for i in range(len(group))]
    
    coords = group[['lng', 'lat']].values
    coords_normalized = (coords - coords.min(axis=0)) / (coords.ptp(axis=0) + 1e-10)
    
    try:
        labels = fclusterdata(coords_normalized, t=radius * 111000, criterion='distance')
        return [group[labels == l] for l in np.unique(labels)]
    except:
        return [group]


def cluster_by_latitude(df, radius):
    """按纬度分块聚类"""
    lat_bins = np.linspace(df['lat'].min(), df['lat'].max(), 60)
    profiles = []
    
    for i in range(len(lat_bins) - 1):
        mask = (df['lat'] >= lat_bins[i]) & (df['lat'] < lat_bins[i+1])
        sub = df[mask].sort_values('lng')
        
        if len(sub) > 0:
            # 按经度分剖面
            lng_bins = np.linspace(sub['lng'].min(), sub['lng'].max(), 5)
            for j in range(len(lng_bins) - 1):
                sub_mask = (sub['lng'] >= lng_bins[j]) & (sub['lng'] < lng_bins[j+1])
                sub_sub = sub[sub_mask]
                if len(sub_sub) > 0:
                    sub_sub = sub_sub.copy()
                    sub_sub['profile_id'] = f"lat{i}_lng{j}"
                    profiles.append(sub_sub)
    
    return profiles


# ============================================================================
# 3. 剖面图生成
# ============================================================================

def generate_profile_image(profile_df: pd.DataFrame, profile_id: str, 
                           output_path: str, max_floors: int = 60,
                           floor_height: float = 3.0):
    """
    生成单个街道剖面图
    
    参数:
        profile_df: 该剖面内的建筑DataFrame
        profile_id: 剖面ID
        output_path: 输出路径
        max_floors: 最大显示层数
        floor_height: 每层高度(米)
    """
    if len(profile_df) == 0:
        return False
    
    # 排序 (按经度)
    profile_df = profile_df.sort_values('lng').reset_index(drop=True)
    
    # 估算建筑宽度 (基于密度)
    n_buildings = len(profile_df)
    # 假设街道总宽度约 500m，每栋建筑平均宽度 30-50m
    total_width = min(n_buildings * 40, 500)  # 米
    building_width = total_width / max(n_buildings, 1)
    
    # 估算建筑间距
    road_width = 30  # 道路宽度
    spacing = (500 - n_buildings * building_width - road_width) / (n_buildings + 1)
    spacing = max(spacing, 5)  # 最小间距5米
    
    # 创建图形
    fig_width = max(12, n_buildings * 2)
    fig = plt.figure(figsize=(fig_width, 8))
    
    # 主剖面图
    ax = fig.add_axes([0.05, 0.25, 0.90, 0.65])
    
    # 计算位置
    x_positions = []
    x = road_width / 2  # 从道路开始
    
    for idx, (_, building) in enumerate(profile_df.iterrows()):
        floors = building['floor_count']
        width = building_width
        name = building['building_name']
        if pd.isna(name) or len(str(name)) > 15:
            name = building['address'][:15] if pd.notna(building['address']) else f"B{idx+1}"
        
        height = floors * floor_height
        usage = building['usage_category']
        color = USAGE_COLORS.get(usage, '#7f8c8d')
        
        # 绘制建筑
        rect = FancyBboxPatch(
            (x, 0), width, height,
            boxstyle="round,pad=0.02,rounding_size=1.5",
            facecolor=color, edgecolor='#2c3e50', linewidth=1.5,
            alpha=0.85
        )
        ax.add_patch(rect)
        
        # 标注建筑名称和层数
        ax.text(
            x + width/2, height/2,
            f"{name}\n{floors}F",
            ha='center', va='center',
            fontsize=8, fontweight='bold',
            color='white',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='black', alpha=0.3),
            rotation=90 if height < 30 else 0
        )
        
        # 标注高度
        ax.text(
            x + width/2, height + 2,
            f"{height:.0f}m",
            ha='center', va='bottom',
            fontsize=7, color='#2c3e50'
        )
        
        x_positions.append(x + width/2)
        
        # 间距
        x += width + spacing
    
    # 设置坐标轴
    ax.set_xlim(-10, x + road_width/2)
    ax.set_ylim(0, min(profile_df['floor_count'].max() * floor_height + 10, max_floors * floor_height))
    
    # 添加地面
    ax.axhline(y=0, color='#34495e', linewidth=3, linestyle='-')
    
    # 绘制道路
    road_rect = Rectangle((-5, -2), road_width + 10, 2, 
                         facecolor='#34495e', alpha=0.8)
    ax.add_patch(road_rect)
    ax.text(road_width/2, -1, 'ROAD / 道路', ha='center', va='center',
            fontsize=9, color='white', fontweight='bold')
    
    # 标注宽度和间距
    total_len = x + road_width/2
    ax.annotate('', xy=(total_len, -4), xytext=(0, -4),
                arrowprops=dict(arrowstyle='<->', color='red', lw=1.5))
    ax.text(total_len/2, -5, f'{total_len:.0f}m', ha='center', fontsize=9, color='red')
    
    # 网格
    ax.grid(True, axis='y', alpha=0.3, linestyle='--')
    ax.set_axisbelow(True)
    
    # Y轴 - 高度
    ax.set_ylabel('Height / 高度 (m)', fontsize=11, fontweight='bold')
    y_ticks = range(0, int(ax.get_ylim()[1]) + 1, 15)
    ax.set_yticks(y_ticks)
    ax.set_yticklabels([f'{y}m\n({int(y/floor_height)}F)' for y in y_ticks], fontsize=8)
    
    # X轴 - 距离
    ax.set_xlabel('Distance along street / 沿街距离 (m)', fontsize=11, fontweight='bold')
    ax.set_xticks(x_positions)
    ax.set_xticklabels([f'{xp:.0f}m' for xp in x_positions], rotation=45, ha='right', fontsize=7)
    
    # 标题
    road_name = profile_df['road_name'].iloc[0] if 'road_name' in profile_df.columns else 'Unknown Road'
    ax.set_title(
        f'Street Cross-Section Profile / 街道剖面图\n'
        f'Profile ID: {profile_id} | Road: {road_name} | Buildings: {n_buildings} | '
        f'Max Height: {profile_df["floor_count"].max()}F / {profile_df["floor_count"].max() * floor_height:.0f}m',
        fontsize=11, fontweight='bold', pad=10
    )
    
    # 图例
    legend_elements = [
        mpatches.Patch(facecolor=USAGE_COLORS[cat], edgecolor='#2c3e50', 
                      label=f'{cat}') 
        for cat in USAGE_COLORS if cat in profile_df['usage_category'].values
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=8, framealpha=0.9)
    
    # =========================================================================
    # 下方统计信息
    # =========================================================================
    stats_ax = fig.add_axes([0.05, 0.05, 0.90, 0.15])
    stats_ax.axis('off')
    
    stats_text = []
    stats_text.append("=" * 80 + "\n")
    stats_text.append("Building Statistics / 建筑统计\n")
    stats_text.append("=" * 80 + "\n")
    
    # 基本统计
    stats_text.append(f"Total Buildings: {n_buildings} | Total Floors: {profile_df['floor_count'].sum()} | "
                     f"Avg Floors: {profile_df['floor_count'].mean():.1f} | Max: {profile_df['floor_count'].max()}F\n")
    
    # 用途分布
    usage_counts = profile_df['usage_category'].value_counts()
    stats_text.append("Usage Distribution / 用途分布:\n")
    for usage, count in usage_counts.items():
        pct = count / n_buildings * 100
        stats_text.append(f"  {usage}: {count} ({pct:.1f}%)\n")
    
    # 高度分段
    floor_bins = [(1, 6, 'Low-rise 1-6F'), 
                  (7, 12, 'Mid-rise 7-12F'),
                  (13, 30, 'High-rise 13-30F'),
                  (31, 100, 'Super High-rise 31F+')]
    
    stats_text.append("\nHeight Distribution / 高度分布:\n")
    for low, high, label in floor_bins:
        count = ((profile_df['floor_count'] >= low) & (profile_df['floor_count'] <= high)).sum()
        if count > 0:
            pct = count / n_buildings * 100
            stats_text.append(f"  {label}: {count} ({pct:.1f}%)\n")
    
    stats_text.append("-" * 80 + "\n")
    stats_text.append("Perception Indicators (Estimated from morphology):\n")
    stats_text.append(f"  SCR (Sidewalk Coverage Ratio): {estimate_scr(profile_df):.2f}\n")
    stats_text.append(f"  EWW (Effective Walkable Width): {estimate_eww(profile_df):.1f}m\n")
    stats_text.append(f"  Building Density: {n_buildings / total_len * 100:.1f} per 100m\n")
    
    stats_ax.text(0.02, 0.95, ''.join(stats_text), 
                  transform=stats_ax.transAxes,
                  fontsize=8, fontfamily='monospace',
                  verticalalignment='top')
    
    plt.savefig(output_path, dpi=150, bbox_inches='tight', 
                facecolor='white', edgecolor='none')
    plt.close(fig)
    
    return True


def estimate_scr(profile_df):
    """估算人行道覆盖率 (基于建筑密度和道路宽度)"""
    n_buildings = len(profile_df)
    avg_floors = profile_df['floor_count'].mean()
    
    # 高密度+高层 -> 低人行道覆盖率
    if avg_floors > 20 and n_buildings > 5:
        return 0.30
    elif avg_floors > 10:
        return 0.50
    elif avg_floors > 5:
        return 0.65
    else:
        return 0.75


def estimate_eww(profile_df):
    """估算有效步行宽度 (米)"""
    n_buildings = len(profile_df)
    avg_floors = profile_df['floor_count'].mean()
    
    # 城中村: 窄街道 + 高层 -> 窄人行道
    if avg_floors > 15:
        return 1.5
    elif avg_floors > 8:
        return 2.5
    elif avg_floors > 3:
        return 3.5
    else:
        return 4.5


# ============================================================================
# 4. 批量生成
# ============================================================================

def generate_all_profiles(building_df: pd.DataFrame, n_profiles: int = 400):
    """生成所有剖面图"""
    print(f"\n[3] 生成 {n_profiles} 张剖面图...")
    
    # 策略: 按主要道路分组，然后按纬度和经度切片
    profiles = []
    
    # 从地址提取道路
    building_df = building_df.copy()
    building_df['road_name'] = building_df['address'].apply(extract_road_name)
    
    # 按道路分组
    road_groups = building_df.groupby('road_name', dropna=False)
    
    for road_name, group in road_groups:
        if pd.isna(road_name):
            continue
            
        # 每条道路按纬度切片
        group = group.sort_values('lat')
        lat_bins = np.linspace(group['lat'].min(), group['lat'].max(), 
                               max(2, len(group) // 10 + 1))
        
        for i in range(len(lat_bins) - 1):
            mask = (group['lat'] >= lat_bins[i]) & (group['lat'] < lat_bins[i+1])
            segment = group[mask]
            
            if len(segment) >= 3:  # 至少3栋建筑
                profiles.append(segment)
    
    # 无道路名称的建筑 - 按空间分块
    nameless = building_df[building_df['road_name'].isna()]
    if len(nameless) > 0:
        lat_bins = np.linspace(nameless['lat'].min(), nameless['lat'].max(), 30)
        for i in range(len(lat_bins) - 1):
            mask = (nameless['lat'] >= lat_bins[i]) & (nameless['lat'] < lat_bins[i+1])
            segment = nameless[mask]
            
            if len(segment) >= 3:
                # 再按经度分
                lng_bins = np.linspace(segment['lng'].min(), segment['lng'].max(), 5)
                for j in range(len(lng_bins) - 1):
                    sub_mask = (segment['lng'] >= lng_bins[j]) & (segment['lng'] < lng_bins[j+1])
                    sub = segment[sub_mask]
                    if len(sub) >= 3:
                        profiles.append(sub)
    
    # 选择前 n_profiles 个剖面
    profiles = profiles[:n_profiles]
    
    print(f"  共生成 {len(profiles)} 个剖面分组")
    
    # 生成图像
    success_count = 0
    failed_count = 0
    
    for i, profile_df in enumerate(tqdm(profiles, desc="Generating profiles")):
        profile_id = f"PROFILE_{i+1:04d}"
        
        # 生成道路名称
        road = profile_df['road_name'].iloc[0] if 'road_name' in profile_df.columns else 'Unknown'
        if pd.isna(road):
            road = 'Mixed_Area'
        road = str(road).replace('/', '_').replace('\\', '_')[:20]
        
        filename = f"{profile_id}_{road}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        try:
            if generate_profile_image(profile_df, profile_id, output_path):
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            failed_count += 1
            if failed_count <= 5:
                print(f"  Error generating {profile_id}: {e}")
    
    print(f"\n  成功: {success_count} 张")
    print(f"  失败: {failed_count} 张")
    
    return profiles


# ============================================================================
# 5. 汇总报告
# ============================================================================

def generate_summary_report(building_df: pd.DataFrame, profiles: list):
    """生成汇总报告"""
    print("\n[4] 生成汇总报告...")
    
    report_path = os.path.join(OUTPUT_DIR, 'profile_summary.csv')
    
    summary_data = []
    for i, profile_df in enumerate(profiles):
        road = profile_df['road_name'].iloc[0] if 'road_name' in profile_df.columns else 'Unknown'
        if pd.isna(road):
            road = 'Mixed'
        
        summary_data.append({
            'profile_id': f'PROFILE_{i+1:04d}',
            'road_name': road,
            'n_buildings': len(profile_df),
            'total_floors': profile_df['floor_count'].sum(),
            'avg_floors': profile_df['floor_count'].mean(),
            'max_floors': profile_df['floor_count'].max(),
            'min_floors': profile_df['floor_count'].min(),
            'dominant_usage': profile_df['usage_category'].mode().iloc[0] if len(profile_df) > 0 else 'Unknown',
            'avg_lat': profile_df['lat'].mean(),
            'avg_lng': profile_df['lng'].mean(),
            'scr_estimate': estimate_scr(profile_df),
            'eww_estimate': estimate_eww(profile_df),
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(report_path, index=False, encoding='utf-8-sig')
    print(f"  报告已保存: {report_path}")
    
    # 打印统计
    print(f"\n  剖面图统计:")
    print(f"    总剖面数: {len(summary_df)}")
    print(f"    总建筑数: {summary_df['n_buildings'].sum()}")
    print(f"    平均每剖面建筑: {summary_df['n_buildings'].mean():.1f}")
    print(f"    平均层数范围: {summary_df['avg_floors'].min():.1f} - {summary_df['avg_floors'].max():.1f}")
    
    return summary_df


# ============================================================================
# 主流程
# ============================================================================

def main():
    print("=" * 70)
    print("Street Cross-Section Profile Generator / 街道剖面图生成器")
    print("=" * 70)
    
    # 1. 加载数据
    building_df = load_building_data()
    
    # 2. 生成剖面图
    profiles = generate_all_profiles(building_df, n_profiles=400)
    
    # 3. 汇总报告
    summary_df = generate_summary_report(building_df, profiles)
    
    print("\n" + "=" * 70)
    print(f"完成! 剖面图保存在: {OUTPUT_DIR}")
    print(f"共生成 {len(profiles)} 张剖面图")
    print("=" * 70)
    
    return summary_df


if __name__ == '__main__':
    main()
