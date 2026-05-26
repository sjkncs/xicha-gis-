# -*- coding: utf-8 -*-
"""
=============================================================================
Street Cross-Section Profile Generator for SCI Publications
街道剖面图生成器 - 适配SCI论文标准
=============================================================================

改进:
- 中文字体正确渲染 (SimHei / Noto Sans CJK)
- 高分辨率输出 (300 DPI)
- 简洁专业的配色方案
- 标准化尺寸和标注
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
from matplotlib import font_manager
from scipy.cluster.hierarchy import fclusterdata
import re
from tqdm import tqdm

# ============================================================================
# 路径配置
# ============================================================================

BASE_DIR = r'e:\xicha gis 智能定位\15分钟城市时间贫困研究'
BUILDING_CSV = os.path.join(BASE_DIR, 'building_data', '南山区-房屋楼栋基础数据_2920004003598.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'v2_real_data', 'street_profiles_hq')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ============================================================================
# SCI标准配色 - 简洁专业
# ============================================================================

USAGE_COLORS = {
    'Residential': '#2166AC',      # 深蓝 - 住宅
    'Mixed Residential': '#67A9CF', # 浅蓝 - 商住混合
    'Commercial': '#B2182B',       # 红色 - 商业
    'Industrial': '#636363',         # 灰色 - 工业
    'Infrastructure': '#F4A582',    # 橙色 - 基础设施
    'Public': '#1A9850',            # 绿色 - 公共设施
    'Other': '#BFBFBF',
    'Unknown': '#D9D9D9',
}

USAGE_TYPE_MAP = {
    1: 'Residential', 2: 'Residential', 3: 'Mixed Residential',
    4: 'Commercial', 5: 'Industrial', 6: 'Infrastructure',
    7: 'Other', 8: 'Public', 0: 'Unknown',
}

# ============================================================================
# 字体配置
# ============================================================================

def setup_chinese_fonts():
    """配置中文字体"""
    # 尝试多个中文字体
    font_paths = [
        'C:/Windows/Fonts/simhei.ttf',      # 黑体
        'C:/Windows/Fonts/simsun.ttc',      # 宋体
        'C:/Windows/Fonts/STKAITI.TTF',      # 楷体
        'C:/Windows/Fonts/STSONG.TTF',       # 宋体
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    ]
    
    chinese_font = None
    for path in font_paths:
        if os.path.exists(path):
            try:
                prop = font_manager.FontProperties(fname=path)
                font_manager.fontManager.addfont(path)
                chinese_font = path
                print(f"  Found Chinese font: {path}")
                break
            except:
                continue
    
    if chinese_font:
        plt.rcParams['font.family'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    else:
        print("  Warning: Chinese font not found, using default")
    
    plt.rcParams['axes.unicode_minus'] = False
    return chinese_font


# ============================================================================
# 数据加载
# ============================================================================

def load_building_data():
    """加载楼栋数据"""
    print("[1] Loading building data...")
    df = pd.read_csv(BUILDING_CSV, dtype=str, keep_default_na=False)
    
    df['gcj_lng'] = pd.to_numeric(df['中心坐标'], errors='coerce')
    df['gcj_lat'] = pd.to_numeric(df['中心点坐标'], errors='coerce')
    df['usage_type'] = pd.to_numeric(df['使用用途'], errors='coerce').fillna(0).astype(int)
    df['floor_count'] = pd.to_numeric(df['总层数'], errors='coerce').fillna(0).astype(int)
    df['building_name'] = df['名称'].str.strip()
    df['address'] = df['常用地址'].str.strip()
    
    df = df.dropna(subset=['gcj_lng', 'gcj_lat'])
    df = df[df['floor_count'] > 0]
    df['lng'] = df['gcj_lng']
    df['lat'] = df['gcj_lat']
    df['usage_category'] = df['usage_type'].map(lambda x: USAGE_TYPE_MAP.get(x, 'Unknown'))
    
    print(f"  Valid buildings: {len(df)}")
    return df


# ============================================================================
# 道路名称提取
# ============================================================================

def extract_road_name(address):
    """从地址中提取道路名称"""
    if pd.isna(address):
        return None
    
    patterns = [
        r'([\u4e00-\u9fa5]+大道)',
        r'([\u4e00-\u9fa5]+路)',
        r'([\u4e00-\u9fa5]+街)',
        r'([\u4e00-\u9fa5]+巷)',
        r'([\u4e00-\u9fa5]+道)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, str(address))
        if match:
            return match.group(1)
    return None


# ============================================================================
# 剖面图生成 - SCI版本
# ============================================================================

def generate_sci_profile(profile_df: pd.DataFrame, profile_id: str, 
                         road_name: str, output_path: str,
                         floor_height: float = 3.0):
    """
    生成SCI标准的街道剖面图
    
    参数:
        profile_df: 建筑数据
        profile_id: 剖面ID
        road_name: 道路名称
        output_path: 输出路径
        floor_height: 层高(米)
    """
    if len(profile_df) == 0:
        return False
    
    # 跳过太少的建筑
    if len(profile_df) < 1:
        return False
    
    profile_df = profile_df.sort_values('lng').reset_index(drop=True)
    
    # SCI标准尺寸
    fig_width_cm = 17.0
    fig_height_cm = 8.0
    fig_dpi = 300
    
    fig = plt.figure(figsize=(fig_width_cm / 2.54, fig_height_cm / 2.54))
    
    # 主剖面图
    ax = fig.add_axes([0.08, 0.15, 0.88, 0.72])
    
    # 计算布局
    n = len(profile_df)
    road_width = 15
    building_width = max(30, min(50, 400 / max(n, 1)))
    spacing = max(5, (300 - n * building_width) / max(n + 1, 1))
    
    x_positions = []
    x = road_width / 2
    buildings = []
    
    for idx, (_, b) in enumerate(profile_df.iterrows()):
        floors = b['floor_count']
        width = building_width
        name = str(b['building_name'])[:12] if pd.notna(b['building_name']) else f"B{idx+1}"
        height = floors * floor_height
        usage = b['usage_category']
        color = USAGE_COLORS.get(usage, '#636363')
        
        # 绘制建筑
        rect = FancyBboxPatch(
            (x, 0), width, height,
            boxstyle="round,pad=0.01,rounding_size=1.0",
            facecolor=color, edgecolor='white', linewidth=0.8,
            alpha=0.9
        )
        ax.add_patch(rect)
        
        # 层数标注
        if height > 20:
            ax.text(x + width/2, height/2, f"{floors}F",
                   ha='center', va='center', fontsize=6,
                   color='white', fontweight='bold')
        
        x_positions.append(x + width/2)
        buildings.append({'name': name, 'floors': floors, 'height': height})
        
        x += width + spacing
    
    # 道路
    road_rect = Rectangle((-2, -1), road_width + 4, 1,
                         facecolor='#404040', edgecolor='none', alpha=0.9)
    ax.add_patch(road_rect)
    
    # 地面线
    ax.axhline(y=0, color='#404040', linewidth=2)
    
    # 标注道路
    ax.text(road_width/2, -0.5, 'Road', ha='center', va='top',
            fontsize=7, color='white', fontweight='bold')
    
    # 设置坐标轴
    total_width = x + road_width/2
    ax.set_xlim(-5, total_width + 5)
    ax.set_ylim(-2, min(profile_df['floor_count'].max() * floor_height + 15, 240))
    
    # Y轴 - 高度
    y_max = ax.get_ylim()[1]
    y_ticks = range(0, int(y_max) + 1, 30)
    ax.set_yticks(list(y_ticks))
    ax.set_yticklabels([f'{y}m' for y in y_ticks], fontsize=7)
    ax.set_ylabel('Height (m)', fontsize=8, fontweight='bold')
    
    # X轴
    ax.set_xticks(x_positions)
    ax.set_xticklabels([f'{i+1}' for i in range(len(x_positions))], fontsize=6)
    ax.set_xlabel('Building Number', fontsize=8, fontweight='bold')
    
    # 标题
    ax.set_title(f'Street Cross-Section: {road_name} ({profile_id})\n'
                  f'n={n} buildings, max={profile_df["floor_count"].max()}F',
                  fontsize=9, fontweight='bold', pad=8)
    
    # 网格
    ax.grid(True, axis='y', alpha=0.3, linestyle=':', color='gray')
    ax.set_axisbelow(True)
    
    # 边框
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)
    
    # 图例
    legend_patches = []
    for usage, color in USAGE_COLORS.items():
        if usage in profile_df['usage_category'].values:
            legend_patches.append(
                mpatches.Patch(facecolor=color, edgecolor='white', 
                             linewidth=0.5, label=usage)
            )
    ax.legend(handles=legend_patches, loc='upper right', fontsize=6,
             framealpha=0.95, edgecolor='gray')
    
    # =========================================================================
    # 下方统计表
    # =========================================================================
    stats_ax = fig.add_axes([0.08, 0.02, 0.88, 0.10])
    stats_ax.axis('off')
    
    # 基本统计
    avg_floors = profile_df['floor_count'].mean()
    max_floors = profile_df['floor_count'].max()
    total_area = n * building_width * avg_floors * floor_height
    
    # 估算SCR和EWW
    if avg_floors > 15:
        scr, eww = 0.30, 1.5
    elif avg_floors > 8:
        scr, eww = 0.50, 2.5
    elif avg_floors > 3:
        scr, eww = 0.65, 3.5
    else:
        scr, eww = 0.75, 4.5
    
    stats_text = (
        f"n={n}  "
        f"Avg floors={avg_floors:.1f}  "
        f"Max={max_floors}F  "
        f"Avg height={avg_floors*floor_height:.0f}m  "
        f"SCR~{scr:.2f}  "
        f"EWW~{eww:.1f}m  "
        f"Density={n/(total_width/100):.1f}/100m"
    )
    
    stats_ax.text(0.5, 0.5, stats_text, transform=stats_ax.transAxes,
                  ha='center', va='center', fontsize=7,
                  bbox=dict(boxstyle='round,pad=0.3', facecolor='#f0f0f0',
                           edgecolor='gray', alpha=0.9))
    
    # 保存 - SCI标准
    plt.savefig(output_path, dpi=fig_dpi, bbox_inches='tight',
                facecolor='white', edgecolor='none',
                format='png', pil_kwargs={'compression': 9})
    plt.close(fig)
    
    return True


# ============================================================================
# 按道路批量生成
# ============================================================================

def generate_profiles_by_road(building_df: pd.DataFrame, target_count: int = 144):
    """按道路生成剖面图"""
    print(f"\n[2] Generating {target_count} profiles by road...")
    
    building_df = building_df.copy()
    building_df['road_name'] = building_df['address'].apply(extract_road_name)
    
    # 统计各道路建筑数
    road_counts = building_df.groupby('road_name', dropna=False).size()
    major_roads = road_counts[road_counts >= 10].sort_values(ascending=False)
    
    print(f"  Major roads (>10 buildings): {len(major_roads)}")
    
    profiles = []
    
    # 策略1: 按道路名分组，每条路用滑动窗口
    for road, count in major_roads.items():
        if pd.isna(road):
            continue
        
        group = building_df[building_df['road_name'] == road].sort_values('lng').reset_index(drop=True)
        if len(group) < 1:
            continue
        
        # 滑动窗口: 窗口20，步长5
        window_size = min(20, max(5, len(group) // 3))
        step = max(3, window_size // 4)
        
        for start in range(0, len(group) - window_size + 1, step):
            end = start + window_size
            segment = group.iloc[start:end]
            if len(segment) >= 2:
                profiles.append((segment, road))
        
        # 如果剩余不足一个窗口但 >= 2
        if len(group) % step != 0:
            last_start = ((len(group) - window_size) // step + 1) * step
            if last_start < len(group) - window_size + 1:
                segment = group.iloc[max(0, len(group) - window_size):]
                if len(segment) >= 2 and segment not in [p[0] for p in profiles[-10:]]:
                    profiles.append((segment, road))
    
    # 策略2: 无道路名称的建筑使用滑动窗口
    nameless = building_df[building_df['road_name'].isna()].sort_values('lng').reset_index(drop=True)
    if len(nameless) >= 2:
        window_size = min(15, max(5, len(nameless) // 5))
        step = max(3, window_size // 3)
        
        for start in range(0, len(nameless) - window_size + 1, step):
            end = start + window_size
            segment = nameless.iloc[start:end]
            if len(segment) >= 2:
                profiles.append((segment, 'Mixed Area'))
    
    # 选择目标数量
    profiles = profiles[:target_count]
    print(f"  Total segments: {len(profiles)}")
    
    # 生成图像
    success = 0
    failed = 0
    
    for i, (segment, road) in enumerate(tqdm(profiles, desc="Generating")):
        profile_id = f"P{i+1:04d}"
        safe_road = str(road).replace('/', '_')[:15]
        filename = f"{profile_id}_{safe_road}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        
        try:
            if generate_sci_profile(segment, profile_id, road, output_path):
                success += 1
        except Exception as e:
            failed += 1
            if failed <= 3:
                print(f"\n  Error: {e}")
    
    print(f"\n  Success: {success}, Failed: {failed}")
    return profiles


# ============================================================================
# 生成汇总报告
# ============================================================================

def generate_summary_csv(profiles: list, building_df: pd.DataFrame):
    """生成剖面汇总表"""
    print("\n[3] Generating summary CSV...")
    
    data = []
    for i, (segment, road) in enumerate(profiles):
        avg_floors = segment['floor_count'].mean()
        
        if avg_floors > 15:
            scr, eww = 0.30, 1.5
        elif avg_floors > 8:
            scr, eww = 0.50, 2.5
        elif avg_floors > 3:
            scr, eww = 0.65, 3.5
        else:
            scr, eww = 0.75, 4.5
        
        data.append({
            'Profile_ID': f'P{i+1:04d}',
            'Road_Name': road,
            'N_Buildings': len(segment),
            'Total_Floors': segment['floor_count'].sum(),
            'Avg_Floors': round(avg_floors, 1),
            'Max_Floors': segment['floor_count'].max(),
            'Min_Floors': segment['floor_count'].min(),
            'Avg_Height_m': round(avg_floors * 3.0, 1),
            'Max_Height_m': segment['floor_count'].max() * 3.0,
            'Dominant_Usage': segment['usage_category'].mode().iloc[0],
            'SCR_Est': scr,
            'EWW_Est_m': eww,
            'Building_Density_per_100m': round(len(segment) / 0.5, 1),
            'Center_Lat': round(segment['lat'].mean(), 6),
            'Center_Lng': round(segment['lng'].mean(), 6),
        })
    
    df = pd.DataFrame(data)
    output_path = os.path.join(OUTPUT_DIR, 'profile_summary.csv')
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"  Saved: {output_path}")
    
    return df


# ============================================================================
# 主流程
# ============================================================================

def main():
    print("=" * 60)
    print("Street Cross-Section Profile Generator (SCI Version)")
    print("=" * 60)
    
    # 配置字体
    setup_chinese_fonts()
    
    # 加载数据
    building_df = load_building_data()
    
    # 生成剖面图
    profiles = generate_profiles_by_road(building_df, target_count=400)
    
    # 生成汇总
    summary_df = generate_summary_csv(profiles, building_df)
    
    print("\n" + "=" * 60)
    print(f"Done! Output: {OUTPUT_DIR}")
    print(f"Total: {len(profiles)} profiles")
    print("=" * 60)


if __name__ == '__main__':
    main()
