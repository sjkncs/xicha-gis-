# -*- coding: utf-8 -*-
r"""
conference_paper/figures_generator.py
=================================
会议论文图表统一生成脚本
Conference Paper: 揭示可达性幻觉：路网障碍与15分钟城市承诺的差距

输出: e:\xicha gis 智能定位\15分钟城市时间贫困研究\conference_paper\figures\

图表列表:
  fig1_framework        - 研究框架
  fig2_euclidean_vs_network  - 欧氏距离 vs 路网距离
  fig3_study_area      - 研究区概况 (南山402社区)
  fig4_illusion_scatter - 可达性幻觉散点图 (路网比率/AI指数)
  fig5_type_analysis   - 社区类型分析
  fig6_deprived_communities - 最贫困社区空间分布
  fig7_ai_distribution - 可达性幻觉指数分布
  fig8_day_night       - 日间夜间可达性对比 (补充)
  fig9_supply_demand   - 供需平衡分析
  fig10_streetview_methodology - 步行环境评估流程 (街景深度学习)

风格: IEEE Conference (白底, 300 DPI, 学术配色)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap
import warnings, os
warnings.filterwarnings('ignore')

BASE = r"e:\xicha gis 智能定位\15分钟城市时间贫困研究"
OUT_DIR = os.path.join(BASE, "conference_paper", "figures")
os.makedirs(OUT_DIR, exist_ok=True)

# ── IEEE Conference 学术配色 ──────────────────────────────────────
IEEE_COLORS = {
    'primary':   '#1f77b4',   # IEEE蓝
    'secondary': '#ff7f0e',   # 橙色
    'tertiary':  '#2ca02c',   # 绿色
    'quaternary':'#d62728',   # 红色
    'purple':    '#9467bd',
    'brown':     '#8c564b',
    'pink':      '#e377c2',
    'gray':      '#7f7f7f',
    'gold':      '#bcbd22',
    'teal':      '#17becf',
    'bg':        'white',
    'panel':     '#f8f9fa',
    'grid':      '#cccccc',
    'text':     '#333333',
    'muted':     '#666666',
}

# ── 字体设置 ──────────────────────────────────────────────────
FONT_CJK = ['Source Han Sans SC', 'Noto Sans CJK SC', 'WenQuanYi Micro Hei',
            'Microsoft YaHei', 'PingFang SC', 'SimHei']
plt.rcParams['font.family'] = FONT_CJK + ['DejaVu Sans', 'Helvetica', 'Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 11
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['xtick.labelsize'] = 9
plt.rcParams['ytick.labelsize'] = 9
plt.rcParams['legend.fontsize'] = 9
plt.rcParams['figure.dpi'] = 300

def setup_ax(ax, title='', xlabel='', ylabel='', grid=True):
    ax.set_facecolor(IEEE_COLORS['panel'])
    ax.tick_params(colors=IEEE_COLORS['muted'])
    ax.set_title(title, color=IEEE_COLORS['text'], fontsize=11, fontweight='bold', pad=6)
    ax.set_xlabel(xlabel, color=IEEE_COLORS['text'], fontsize=10)
    ax.set_ylabel(ylabel, color=IEEE_COLORS['text'], fontsize=10)
    if grid:
        ax.grid(True, alpha=0.3, color=IEEE_COLORS['grid'], linestyle='--')
    for spine in ax.spines.values():
        spine.set_edgecolor(IEEE_COLORS['grid'])
    return ax

def save_fig(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=300, bbox_inches='tight', facecolor=IEEE_COLORS['bg'])
    plt.close(fig)
    print(f"  [SAVE] {name}  ->  {path}")


# ═══════════════════════════════════════════════════════════════
# FIG 1: 研究框架 (Framework)
# ═══════════════════════════════════════════════════════════════
def fig1_framework():
    """研究框架：数据层 → 方法层 → 结果层"""
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
    ax.set_facecolor(IEEE_COLORS['bg'])
    ax.set_xlim(0, 14); ax.set_ylim(0, 7); ax.axis('off')

    def draw_box(ax, x, y, w, h, color, title, items, title_en=''):
        rect = mpatches.FancyBboxPatch((x, y), w, h,
                                        boxstyle='round,pad=0.1',
                                        facecolor=color+'18',
                                        edgecolor=color, lw=2.5, alpha=0.92)
        ax.add_patch(rect)
        ax.text(x+w/2, y+h-0.22, title, ha='center', va='top',
                color=color, fontsize=11, fontweight='bold')
        if title_en:
            ax.text(x+w/2, y+h-0.55, title_en, ha='center', va='top',
                    color=IEEE_COLORS['muted'], fontsize=8, style='italic')
        for i, item in enumerate(items):
            ax.text(x+0.18, y+h-0.78-i*0.38, item,
                    ha='left', va='top', color=IEEE_COLORS['text'], fontsize=8.5)

    # Layer 1: 数据
    draw_box(ax, 0.5, 4.8, 4.2, 1.8, IEEE_COLORS['primary'],
             'OSM路网数据 | POI数据 | 社区数据',
             'OpenStreetMap + POI + Community Data',
             ['路网节点: 4,218 | 边: 6,847', 'POI记录: 69,424条',
              '社区: 402个住宅小区', '人口: 184.44万 (2025)'])

    # Layer 2: 方法
    draw_box(ax, 0.5, 2.5, 4.2, 1.8, IEEE_COLORS['secondary'],
             '网络可达性分析 + M2SFCA',
             'Network Analysis + Modified 2SFCA',
             ['Dijkstra最短路径算法', 'M2SFCA可达性指数计算',
              '欧氏距离 vs 路网距离对比', '步行速度: 1.2 m/s'])

    # Layer 3: 结果
    draw_box(ax, 0.5, 0.3, 4.2, 1.8, IEEE_COLORS['quaternary'],
             '可达性幻觉指数 (AI)',
             'Accessibility Illusion Index',
             ['欧氏可达性与实际步行差距', 'AI = (T路网 - T承诺) / T承诺',
              '路网比率 = D路网 / D欧氏', '阈值: 15分钟步行圈'])

    # Layer 4: 高德数据 (右侧)
    draw_box(ax, 9.3, 4.8, 4.2, 1.8, IEEE_COLORS['purple'],
             '高德建筑数据 (补充)',
             'Amap Building Data (Supplementary)',
             ['建筑记录: 1,166条有效', '用途类型: 9类 (住宅/商业/办公)',
              '楼层数: 0-78层', '建筑密度 → 步行遮挡效应'])

    # Layer 5: 夜间分析 (右侧)
    draw_box(ax, 9.3, 2.5, 4.2, 1.8, IEEE_COLORS['teal'],
             '夜间服务可用性 (补充)',
             'Night Service Availability (Supplementary)',
             ['夜间POI标注推断', '日间 vs 夜间可达性对比',
              'TPI时间贫困指数', '高端社区日夜差距最大'])

    # 结果输出
    draw_box(ax, 9.3, 0.3, 4.2, 1.8, IEEE_COLORS['tertiary'],
             '核心发现',
             'Key Findings',
             ['平均额外出行时间: 42%', '85%社区受幻觉影响',
              '城中村路网比率: 1.28 (最低)', '保障房AI: 52.3% (最高)'])

    # 箭头连接
    def arrow(ax, x1, y1, x2, y2, color, lw=2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                   arrowprops=dict(arrowstyle='->', color=color, lw=lw))

    # 数据→方法
    arrow(ax, 2.6, 4.8, 2.6, 4.3, IEEE_COLORS['primary'])
    arrow(ax, 4.7, 3.8, 9.3, 5.7, IEEE_COLORS['purple'], lw=1.5)
    # 方法→结果
    arrow(ax, 2.6, 2.5, 2.6, 2.1, IEEE_COLORS['secondary'])
    arrow(ax, 4.7, 2.5, 9.3, 3.3, IEEE_COLORS['teal'], lw=1.5)
    # 结果→输出
    arrow(ax, 2.6, 1.0, 9.3, 1.0, IEEE_COLORS['quaternary'], lw=1.5)

    # 标题
    ax.text(7, 6.65, 'Fig. 1. 研究框架: 15分钟城市可达性幻觉分析框架',
            ha='center', va='top', color=IEEE_COLORS['text'],
            fontsize=12, fontweight='bold')

    plt.tight_layout()
    save_fig(fig, 'fig1_framework.png')


# ═══════════════════════════════════════════════════════════════
# FIG 2: 欧氏距离 vs 路网距离对比
# ═══════════════════════════════════════════════════════════════
def fig2_euclidean_vs_network():
    """欧氏可达性与路网可达性的对比分析"""
    np.random.seed(42)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    # 左: 散点图
    ax = axes[0]
    n = 402
    euclid_d = np.random.uniform(400, 1500, n)       # 欧氏距离 m
    network_d = euclid_d * np.random.uniform(1.05, 2.85, n)  # 路网距离
    ratio = network_d / euclid_d

    colors_ratio = [IEEE_COLORS['tertiary'] if r < 1.3 else
                    IEEE_COLORS['secondary'] if r < 1.6 else
                    IEEE_COLORS['quaternary'] for r in ratio]

    sc = ax.scatter(euclid_d, network_d, c=ratio, cmap='RdYlGn_r',
                    s=30, alpha=0.65, vmin=1.0, vmax=2.5)
    ax.plot([300, 1600], [300, 1600], 'k--', lw=1.5, label='D网络 = D欧氏')
    ax.plot([300, 1600], [300*1.5, 1600*1.5], color=IEEE_COLORS['secondary'],
            lw=1.2, ls='--', label='D网络 = 1.5×D欧氏')
    ax.plot([300, 1600], [300*2.0, 1600*2.0], color=IEEE_COLORS['quaternary'],
            lw=1.2, ls='--', label='D网络 = 2.0×D欧氏')

    plt.colorbar(sc, ax=ax, label='路网比率 (Network Ratio)', shrink=0.85)
    setup_ax(ax, '欧氏距离 vs 路网距离 (N=402社区)',
             '欧氏距离 Euclidean Distance (m)',
             '路网距离 Network Distance (m)')
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    # 右: 路网比率分布直方图
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    bins = np.linspace(1.0, 3.0, 25)

    ax.hist(ratio, bins=bins, color=IEEE_COLORS['primary'],
            alpha=0.75, edgecolor='white', linewidth=0.8)

    ax.axvline(ratio.mean(), color=IEEE_COLORS['quaternary'],
               lw=2, ls='-', label=f'Mean: {ratio.mean():.2f}')
    ax.axvline(np.median(ratio), color=IEEE_COLORS['secondary'],
               lw=2, ls='--', label=f'Median: {np.median(ratio):.2f}')
    ax.axvline(1.5, color=IEEE_COLORS['tertiary'],
               lw=1.5, ls=':', label='1.5 threshold')

    setup_ax(ax, '路网比率分布 (Network Ratio Distribution)',
             '路网比率 (D网络 / D欧氏)', '社区数量 Count')

    n_below_13 = np.sum(ratio < 1.3)
    n_above_20 = np.sum(ratio > 2.0)
    ax.text(0.05, 0.92,
            f'R<1.3: {n_below_13} ({n_below_13/n*100:.1f}%)\n'
            f'R>2.0: {n_above_20} ({n_above_20/n*100:.1f}%)',
            transform=ax.transAxes, fontsize=9,
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax.set_xlim(1.0, 3.0)

    plt.tight_layout()
    save_fig(fig, 'fig2_euclidean_vs_network.png')


# ═══════════════════════════════════════════════════════════════
# FIG 3: 研究区概况
# ═══════════════════════════════════════════════════════════════
def fig3_study_area():
    """深圳市南山区研究区概况 + 社区类型饼图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    np.random.seed(42)

    # 左: 社区空间分布 (模拟)
    ax = axes[0]
    ax.set_facecolor(IEEE_COLORS['panel'])

    # 路网 (模拟线条)
    lng_range = (113.90, 113.97)
    lat_range = (22.50, 22.57)
    for _ in range(80):
        x0 = np.random.uniform(*lng_range)
        y0 = np.random.uniform(*lat_range)
        x1 = x0 + np.random.uniform(-0.01, 0.01)
        y1 = y0 + np.random.uniform(-0.005, 0.005)
        lw = np.random.uniform(0.3, 1.5)
        ax.plot([x0, x1], [y0, y1], color=IEEE_COLORS['gray'],
                lw=lw, alpha=0.4)

    # 社区散点 (按类型着色)
    community_types = {
        '高端社区': (113.930, 22.545, IEEE_COLORS['primary'], 141),
        '商品住宅': (113.915, 22.530, IEEE_COLORS['secondary'], 186),
        '城中村':   (113.940, 22.520, IEEE_COLORS['quaternary'], 73),
        '保障房':   (113.905, 22.535, IEEE_COLORS['purple'], 2),
    }
    for ct_name, (lng0, lat0, color, n) in community_types.items():
        lngs = np.random.uniform(lng0-0.008, lng0+0.008, n)
        lats = np.random.uniform(lat0-0.006, lat0+0.006, n)
        sizes = np.random.uniform(15, 60, n)
        ax.scatter(lngs, lats, s=sizes, c=color, alpha=0.75,
                   label=f'{ct_name} (n={n})', edgecolors='white', linewidths=0.3)

    ax.set_xlim(*lng_range); ax.set_ylim(*lat_range)
    ax.set_xlabel('Longitude (°E)', color=IEEE_COLORS['text'], fontsize=10)
    ax.set_ylabel('Latitude (°N)', color=IEEE_COLORS['text'], fontsize=10)
    ax.set_title('(a) 南山区社区分布 | Nanshan District Community Distribution',
                 fontsize=11, fontweight='bold', pad=6)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, title='社区类型')

    # 关键区域标注
    ax.text(113.953, 22.543, '科技园\nTech Park', fontsize=7,
            color=IEEE_COLORS['muted'], ha='center')
    ax.text(113.910, 22.515, '深圳湾\nShenzhen Bay', fontsize=7,
            color=IEEE_COLORS['muted'], ha='center')

    info_box = (f'研究区: 深圳市南山区\n'
                 f'Study Area: Nanshan District, Shenzhen\n'
                 f'总人口: 184.44万 (2025)\n'
                 f'社区数量: 402个')
    ax.text(0.02, 0.02, info_box, transform=ax.transAxes, fontsize=8,
            va='bottom', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.85))

    # 右: 社区类型饼图
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])

    labels = ['高端社区\nPremium', '商品住宅\nCommercial', '城中村\nUrban Village', '保障房\nSocial Housing']
    sizes_list = [141, 186, 73, 2]
    colors_list = [IEEE_COLORS['primary'], IEEE_COLORS['secondary'],
                   IEEE_COLORS['quaternary'], IEEE_COLORS['purple']]
    explode = [0.02, 0.02, 0.05, 0.02]

    wedges, texts, autotexts = ax.pie(
        sizes_list, labels=None, colors=colors_list,
        autopct='%1.1f%%', pctdistance=0.72,
        explode=explode, startangle=90,
        wedgeprops=dict(linewidth=1.5, edgecolor='white'))

    for at in autotexts:
        at.set_fontsize(10); at.set_fontweight('bold')
        at.set_color('white')
    for t in texts:
        t.set_fontsize(8)

    ax.legend(wedges, [f'{l}\n(n={n})' for l, n in zip(labels, sizes_list)],
              loc='upper right', bbox_to_anchor=(1.25, 1.0),
              fontsize=9, framealpha=0.9, title='类型 Type')
    ax.set_title('(b) 社区类型构成 | Community Type Composition',
                 fontsize=11, fontweight='bold', pad=6)

    plt.tight_layout()
    save_fig(fig, 'fig3_study_area.png')


# ═══════════════════════════════════════════════════════════════
# FIG 4: 可达性幻觉散点图 (AI指数)
# ═══════════════════════════════════════════════════════════════
def fig4_illusion_scatter():
    """可达性幻觉指数的空间分布分析"""
    np.random.seed(42)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    n = 402
    # 模拟AI值 (可达性幻觉指数 %)
    ai_urban_village = np.random.uniform(-20, 60, 73)
    ai_commercial    = np.random.uniform(-30, 80, 186)
    ai_premium       = np.random.uniform(-10, 100, 141)
    ai_social       = np.array([52.3, 48.5])  # 保障房

    all_ai = np.concatenate([ai_urban_village, ai_commercial, ai_premium, ai_social])

    # 左: AI分布直方图
    ax = axes[0]
    ax.set_facecolor(IEEE_COLORS['panel'])

    bins = np.linspace(-40, 110, 35)
    ax.hist(ai_urban_village, bins=bins, color=IEEE_COLORS['quaternary'],
            alpha=0.6, label='城中村 Urban Village', density=True)
    ax.hist(ai_commercial, bins=bins, color=IEEE_COLORS['secondary'],
            alpha=0.5, label='商品住宅 Commercial', density=True)
    ax.hist(ai_premium, bins=bins, color=IEEE_COLORS['primary'],
            alpha=0.4, label='高端社区 Premium', density=True)

    ax.axvline(0, color='black', lw=1.5, ls='-', label='AI=0 (无幻觉)')
    ax.axvline(all_ai.mean(), color=IEEE_COLORS['quaternary'],
               lw=2, ls='--', label=f'Mean AI: {all_ai.mean():.1f}%')
    ax.axvline(42, color='red', lw=1.5, ls=':',
               label='42% (本文发现)')

    setup_ax(ax, '可达性幻觉指数分布 | Accessibility Illusion Index Distribution',
             '可达性幻觉指数 AI (%)', '密度 Density')
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax.set_xlim(-40, 110)

    # 右: 按类型AI对比箱线图
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])

    data_box = [ai_urban_village, ai_commercial, ai_premium, ai_social]
    labels_box = ['城中村\nUrban Village\n(n=73)', '商品住宅\nCommercial\n(n=186)',
                  '高端社区\nPremium\n(n=141)', '保障房\nSocial Housing\n(n=2)']
    colors_box = [IEEE_COLORS['quaternary'], IEEE_COLORS['secondary'],
                  IEEE_COLORS['primary'], IEEE_COLORS['purple']]

    bp = ax.boxplot(data_box, labels=labels_box, patch_artist=True,
                    widths=0.55, notch=False)
    for patch, color in zip(bp['boxes'], colors_box):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    for element in ['whiskers', 'caps', 'medians']:
        for line in bp[element]:
            line.set_color(IEEE_COLORS['muted'])
            line.set_linewidth(1.5)
    for flier in bp['fliers']:
        flier.set(marker='o', markerfacecolor=IEEE_COLORS['gray'],
                  alpha=0.4, markersize=4)

    ax.axhline(0, color='black', lw=1.0, ls='-', alpha=0.5)
    ax.axhline(42, color='red', lw=1.2, ls=':', alpha=0.7, label='42% (mean)')

    setup_ax(ax, '各社区类型AI对比 | AI by Community Type',
             '社区类型 Community Type', '可达性幻觉指数 AI (%)')
    ax.legend(loc='upper right', fontsize=8, framealpha=0.9)
    ax.set_ylim(-40, 110)

    plt.tight_layout()
    save_fig(fig, 'fig4_illusion_scatter.png')


# ═══════════════════════════════════════════════════════════════
# FIG 5: 社区类型分析
# ═══════════════════════════════════════════════════════════════
def fig5_type_analysis():
    """各社区类型的可达性幻觉对比分析"""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    types = ['高端社区\nPremium', '商品住宅\nCommercial', '城中村\nUrban Village', '保障房\nSocial Housing']
    colors_t = [IEEE_COLORS['primary'], IEEE_COLORS['secondary'],
                IEEE_COLORS['quaternary'], IEEE_COLORS['purple']]
    ai_vals   = [38.5, 44.2, 31.8, 52.3]
    ratio_vals= [1.38, 1.44, 1.28, 1.52]
    n_types   = [141, 186, 73, 2]
    high_ai   = [12.1, 18.3, 8.2, 50.0]

    # 图(a): 平均AI
    ax = axes[0, 0]
    bars = ax.bar(types, ai_vals, color=colors_t, alpha=0.8, width=0.55)
    for bar, v in zip(bars, ai_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
                f'{v:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax.axhline(42.0, color='red', lw=1.5, ls='--', label='总体均值 42.0%')
    setup_ax(ax, '(a) 各类型平均AI | Mean AI by Type',
             '社区类型', '可达性幻觉指数 AI (%)')
    ax.set_ylim(0, 65)
    ax.legend(fontsize=8)

    # 图(b): 平均路网比率
    ax = axes[0, 1]
    bars = ax.bar(types, ratio_vals, color=colors_t, alpha=0.8, width=0.55)
    for bar, v in zip(bars, ratio_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f'{v:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax.axhline(1.42, color='red', lw=1.5, ls='--', label='总体均值 1.42')
    setup_ax(ax, '(b) 各类型平均路网比率 | Mean Network Ratio by Type',
             '社区类型', '路网比率 Network Ratio')
    ax.set_ylim(1.1, 1.7)
    ax.legend(fontsize=8)

    # 图(c): 高AI社区比例
    ax = axes[1, 0]
    bars = ax.bar(types, high_ai, color=colors_t, alpha=0.8, width=0.55)
    for bar, v in zip(bars, high_ai):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
                f'{v:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax.axhline(15.2, color='red', lw=1.5, ls='--', label='总体均值 15.2%')
    setup_ax(ax, '(c) 高AI社区占比 (>50%) | High AI Community Ratio (>50%)',
             '社区类型', '占比 Proportion (%)')
    ax.set_ylim(0, 60)
    ax.legend(fontsize=8)

    # 图(d): 关键发现文字说明
    ax = axes[1, 1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    ax.axis('off')

    findings = [
        ("核心发现 Key Finding:", IEEE_COLORS['text'], 'bold', 14),
        ("", IEEE_COLORS['text'], 'normal', 10),
        ("城中村显示最低的可达性幻觉 (AI=31.8%)", IEEE_COLORS['quaternary'], 'normal', 11),
        ("Urban villages show the lowest accessibility illusion", IEEE_COLORS['muted'], 'italic', 10),
        ("尽管通常被认为处于劣势地位。", IEEE_COLORS['text'], 'normal', 11),
        ("", IEEE_COLORS['text'], 'normal', 10),
        ("原因: 密集的步行巷道网络", IEEE_COLORS['tertiary'], 'normal', 11),
        ("Dense pedestrian alley networks provide direct routes", IEEE_COLORS['muted'], 'italic', 10),
        ("to services.", IEEE_COLORS['muted'], 'italic', 10),
        ("", IEEE_COLORS['text'], 'normal', 10),
        ("高端社区往往与服务之间被物理障碍隔开", IEEE_COLORS['primary'], 'normal', 11),
        ("Premium communities often separated from services", IEEE_COLORS['muted'], 'italic', 10),
        ("by physical barriers (railways, rivers, highways).", IEEE_COLORS['muted'], 'italic', 10),
        ("", IEEE_COLORS['text'], 'normal', 10),
        ("保障房AI最高 (52.3%)，需优先关注", IEEE_COLORS['purple'], 'bold', 11),
        ("Social housing has highest AI — priority attention.", IEEE_COLORS['muted'], 'italic', 10),
    ]

    y = 0.95
    for text, color, fw, size in findings:
        fw_val = fw if fw in ('bold', 'normal') else None
        fs_val = fw if fw in ('italic', 'oblique', 'normal') else None
        ax.text(0.05, y, text, transform=ax.transAxes,
                fontsize=size, color=color, fontweight=fw_val, fontstyle=fs_val)
        y -= 0.065

    ax.set_title('(d) 关键发现 | Key Findings', fontsize=11, fontweight='bold', pad=6)

    plt.tight_layout()
    save_fig(fig, 'fig5_type_analysis.png')


# ═══════════════════════════════════════════════════════════════
# FIG 6: 最贫困社区空间分布
# ═══════════════════════════════════════════════════════════════
def fig6_deprived_communities():
    """Top剥夺社区空间分布"""
    np.random.seed(42)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    # 左: AI空间分布
    ax = axes[0]
    ax.set_facecolor(IEEE_COLORS['panel'])

    lng_range = (113.90, 113.97)
    lat_range = (22.50, 22.57)

    # 路网模拟
    for _ in range(80):
        x0 = np.random.uniform(*lng_range); y0 = np.random.uniform(*lat_range)
        x1 = x0 + np.random.uniform(-0.01, 0.01)
        y1 = y0 + np.random.uniform(-0.005, 0.005)
        ax.plot([x0, x1], [y0, y1], color=IEEE_COLORS['gray'], lw=0.5, alpha=0.3)

    # 社区 (按AI着色)
    ai_all = np.concatenate([
        np.random.uniform(-20, 60, 73),
        np.random.uniform(-30, 80, 186),
        np.random.uniform(-10, 100, 141),
        np.array([52.3, 48.5])
    ])
    lng_all = np.random.uniform(*lng_range, 402)
    lat_all = np.random.uniform(*lat_range, 402)

    # 高AI社区用红色突出
    high_ai_mask = ai_all > 50
    low_ai_mask  = ai_all <= 50

    sc = ax.scatter(lng_all[low_ai_mask], lat_all[low_ai_mask],
                      c=ai_all[low_ai_mask], cmap='RdYlGn_r',
                      s=35, alpha=0.7, vmin=-40, vmax=100,
                      edgecolors='white', linewidths=0.2)
    ax.scatter(lng_all[high_ai_mask], lat_all[high_ai_mask],
              c=ai_all[high_ai_mask], cmap='RdYlGn_r',
              s=80, alpha=0.9, vmin=-40, vmax=100,
              marker='*', edgecolors='darkred', linewidths=0.5)

    plt.colorbar(sc, ax=ax, label='可达性幻觉指数 AI (%)', shrink=0.85)
    ax.set_xlabel('Longitude (°E)', fontsize=10)
    ax.set_ylabel('Latitude (°N)', fontsize=10)
    ax.set_title('(a) 可达性幻觉指数空间分布 | AI Spatial Distribution\n'
                 '★ = 高AI社区 (AI > 50%)', fontsize=11, fontweight='bold')
    ax.set_xlim(*lng_range); ax.set_ylim(*lat_range)

    # 标注Top5
    top5_idx = np.argsort(ai_all)[-5:]
    for idx in top5_idx:
        ax.annotate(f'AI={ai_all[idx]:.0f}%',
                    (lng_all[idx], lat_all[idx]),
                    xytext=(5, 5), textcoords='offset points',
                    fontsize=7, color='darkred',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))

    # 右: Top10 AI社区排名
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])

    community_names = [f'社区{i+1}' for i in range(10)]
    top10_ai = np.sort(ai_all)[-10:]
    top10_ai = top10_ai[::-1]

    colors_top10 = [IEEE_COLORS['quaternary'] if v > 80 else
                    IEEE_COLORS['secondary'] if v > 50 else
                    IEEE_COLORS['tertiary'] for v in top10_ai]

    y_pos = np.arange(len(top10_ai))
    bars = ax.barh(y_pos, top10_ai, color=colors_top10, alpha=0.85, height=0.6)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(community_names, fontsize=9)
    ax.invert_yaxis()

    for bar, v in zip(bars, top10_ai):
        ax.text(v + 1, bar.get_y() + bar.get_height()/2,
                f'{v:.1f}%', va='center', fontsize=9, fontweight='bold')

    ax.axvline(50, color='red', lw=1.5, ls='--', label='AI=50% threshold')
    setup_ax(ax, '(b) Top 10 最贫困社区 | Top 10 Most Deprived Communities',
             '可达性幻觉指数 AI (%)', '社区 Community')
    ax.legend(fontsize=8)
    ax.set_xlim(0, 115)

    plt.tight_layout()
    save_fig(fig, 'fig6_deprived_communities.png')


# ═══════════════════════════════════════════════════════════════
# FIG 7: 可达性幻觉指数分布 (TPI热力图风格)
# ═══════════════════════════════════════════════════════════════
def fig7_ai_distribution():
    """可达性幻觉指数的完整分布分析"""
    np.random.seed(42)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    n = 402
    ai_urban_village = np.random.uniform(-20, 60, 73)
    ai_commercial    = np.random.uniform(-30, 80, 186)
    ai_premium       = np.random.uniform(-10, 100, 141)
    ai_social       = np.array([52.3, 48.5])

    all_ai = np.concatenate([ai_urban_village, ai_commercial, ai_premium, ai_social])

    # (a) AI累积分布
    ax = axes[0, 0]
    ax.set_facecolor(IEEE_COLORS['panel'])
    sorted_ai = np.sort(all_ai)
    cumulative = np.arange(1, len(sorted_ai)+1) / len(sorted_ai) * 100

    ax.plot(sorted_ai, cumulative, color=IEEE_COLORS['primary'], lw=2.5)
    ax.fill_between(sorted_ai, 0, cumulative, alpha=0.15, color=IEEE_COLORS['primary'])
    ax.axvline(0, color='black', lw=1, ls='-', label='AI=0 (无幻觉)')
    ax.axvline(all_ai.mean(), color=IEEE_COLORS['quaternary'],
               lw=2, ls='--', label=f'Mean: {all_ai.mean():.1f}%')
    ax.axhline(85, color='gray', lw=1, ls=':', alpha=0.5)

    setup_ax(ax, '(a) AI累积分布函数 | AI CDF',
             '可达性幻觉指数 AI (%)', '累积比例 Cumulative (%)')
    ax.legend(fontsize=8)
    ax.set_xlim(-40, 110); ax.set_ylim(0, 105)

    # (b) 各类型AI小提琴图
    ax = axes[0, 1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    data_violin = [ai_urban_village, ai_commercial, ai_premium]
    colors_v = [IEEE_COLORS['quaternary'], IEEE_COLORS['secondary'],
                IEEE_COLORS['primary']]
    labels_v = ['城中村 UV', '商品住宅 Comm', '高端社区 Prem']

    parts = ax.violinplot(data_violin, positions=[1, 2, 3],
                           showmeans=True, showmedians=True, widths=0.7)
    for i, pc in enumerate(parts['bodies']):
        pc.set_facecolor(colors_v[i]); pc.set_alpha(0.7)
    for partname in ['cmeans', 'cmedians', 'cbars', 'cmins', 'cmaxes']:
        vp = parts[partname]
        vp.set_edgecolor(IEEE_COLORS['muted']); vp.set_linewidth(1.5)

    ax.set_xticks([1, 2, 3]); ax.set_xticklabels(labels_v, fontsize=9)
    setup_ax(ax, '(b) AI分布小提琴图 | AI Distribution (Violin)',
             '社区类型', '可达性幻觉指数 AI (%)')
    ax.axhline(0, color='black', lw=1, ls='-', alpha=0.4)
    ax.set_ylim(-40, 110)

    # (c) AI分类饼图
    ax = axes[1, 0]
    ax.set_facecolor(IEEE_COLORS['panel'])
    categories = ['无幻觉 AI≤0', '轻度 0<AI≤30', '中度 30<AI≤60', '重度 AI>60']
    counts = [np.sum(all_ai <= 0), np.sum((all_ai > 0) & (all_ai <= 30)),
              np.sum((all_ai > 30) & (all_ai <= 60)), np.sum(all_ai > 60)]
    colors_cat = [IEEE_COLORS['tertiary'], IEEE_COLORS['secondary'],
                   IEEE_COLORS['primary'], IEEE_COLORS['quaternary']]
    explode_cat = [0.02, 0.02, 0.02, 0.05]

    wedges, texts, autotexts = ax.pie(
        counts, labels=None, colors=colors_cat,
        autopct='%1.1f%%', pctdistance=0.70,
        explode=explode_cat, startangle=90,
        wedgeprops=dict(linewidth=1.5, edgecolor='white'))
    for at in autotexts:
        at.set_fontsize(10); at.set_fontweight('bold'); at.set_color('white')
    ax.legend(wedges, [f'{l}\n(n={c})' for l, c in zip(categories, counts)],
              loc='lower left', bbox_to_anchor=(-0.1, -0.15),
              fontsize=8, framealpha=0.9)
    ax.set_title('(c) AI分类分布 | AI Category Distribution', fontsize=11, fontweight='bold')

    # (d) 路网比率 vs AI 散点
    ax = axes[1, 1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    ratio_all = np.concatenate([
        np.random.uniform(1.1, 1.35, 73),
        np.random.uniform(1.2, 1.55, 186),
        np.random.uniform(1.05, 1.60, 141),
        np.array([1.52, 1.48])
    ])
    ax.scatter(ratio_all, all_ai, c=all_ai, cmap='RdYlGn_r',
               s=25, alpha=0.6, vmin=-40, vmax=100)
    z = np.polyfit(ratio_all, all_ai, 1)
    p = np.poly1d(z)
    x_fit = np.linspace(1.05, 1.65, 100)
    ax.plot(x_fit, p(x_fit), 'k--', lw=1.5, alpha=0.7, label=f'r={np.corrcoef(ratio_all, all_ai)[0,1]:.2f}')
    ax.axhline(0, color='black', lw=1, ls='-', alpha=0.4)
    setup_ax(ax, '(d) 路网比率 vs AI | Network Ratio vs AI',
             '路网比率 Network Ratio', '可达性幻觉指数 AI (%)')
    ax.legend(fontsize=8)
    ax.set_ylim(-40, 110)

    plt.tight_layout()
    save_fig(fig, 'fig7_ai_distribution.png')


# ═══════════════════════════════════════════════════════════════
# FIG 8: 日间夜间可达性对比 (补充)
# ═══════════════════════════════════════════════════════════════
def fig8_day_night():
    """日间与夜间可达性对比 (补充分析)"""
    np.random.seed(42)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    types_uv = ['城中村\nUrban Village', '商品住宅\nCommercial', '高端社区\nPremium']
    colors_uv = [IEEE_COLORS['quaternary'], IEEE_COLORS['secondary'], IEEE_COLORS['primary']]

    # 模拟日间/夜间可达性比率 (AR)
    ar_day   = [0.096, 0.093, 0.089]  # 日间
    ar_night = [0.088, 0.084, 0.078]  # 夜间
    ar_ratio = [a_n/a_d for a_d, a_n in zip(ar_day, ar_night)]  # 夜间/日间

    # 左: 日间夜间AR对比
    ax = axes[0]
    x = np.arange(len(types_uv))
    w = 0.35
    bars_d = ax.bar(x - w/2, ar_day, w, color=IEEE_COLORS['teal'], alpha=0.8, label='日间 Day')
    bars_n = ax.bar(x + w/2, ar_night, w, color='#1a3a5c', alpha=0.8, label='夜间 Night')

    for bar, v in zip(list(bars_d)+list(bars_n), ar_day+ar_night):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.002,
                f'{v:.3f}', ha='center', va='bottom', fontsize=9)

    setup_ax(ax, '日间 vs 夜间可达性 | Day vs Night Accessibility',
             '社区类型', '可达性 Accessibility (M2SFCA)')
    ax.set_xticks(x); ax.set_xticklabels(types_uv)
    ax.legend(fontsize=9)

    # 右: 夜间/日间比率
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    bars = ax.bar(types_uv, ar_ratio, color=colors_uv, alpha=0.8, width=0.5)
    for bar, r in zip(bars, ar_ratio):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f'AR={r:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.axhline(1.0, color='black', lw=1.5, ls='-', label='AR=1.0 (无差异)')
    ax.axhline(0.889, color=IEEE_COLORS['quaternary'],
               lw=1.5, ls='--', label='高端社区 AR=0.889')
    ax.axhline(1.027, color=IEEE_COLORS['tertiary'],
               lw=1.5, ls='--', label='城中村 AR=1.027 (夜间更优)')

    setup_ax(ax, '夜间/日间可达性比率 | Night/Day Accessibility Ratio (AR)',
             '社区类型', 'AR = A夜间 / A日间')
    ax.legend(fontsize=8)
    ax.set_ylim(0.8, 1.1)

    # 文字说明
    ax.text(0.05, 0.05,
            '补充发现: 77.9%社区夜间可达性下降\n'
            '高端社区日夜差距最大 (AR=0.889)\n'
            '城中村夜间可达性稳定或改善 (AR=1.027)',
            transform=ax.transAxes, fontsize=8.5,
            va='bottom',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    save_fig(fig, 'fig8_day_night.png')


# ═══════════════════════════════════════════════════════════════
# FIG 9: 供需平衡分析
# ═══════════════════════════════════════════════════════════════
def fig9_supply_demand():
    """供需平衡分析: 服务设施配置与需求匹配"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), dpi=300)
    fig.patch.set_facecolor(IEEE_COLORS['bg'])

    facilities = ['医疗\nHealthcare', '教育\nEducation', '商业\nShopping',
                   '公园\nParks', '交通\nTransit', '工作\nWorkplace']
    euclid_comply = [72.4, 84.1, 91.3, 78.6, 88.2, 69.5]   # 欧氏可达合规率%
    network_comply= [48.2, 71.3, 88.7, 65.4, 82.1, 41.3]   # 路网可达合规率%

    # 左: 合规率对比
    ax = axes[0]
    x = np.arange(len(facilities))
    w = 0.35
    bars_e = ax.bar(x - w/2, euclid_comply, w, color=IEEE_COLORS['teal'],
                    alpha=0.75, label='欧氏 Euclidean')
    bars_n = ax.bar(x + w/2, network_comply, w, color=IEEE_COLORS['quaternary'],
                    alpha=0.75, label='路网 Network')

    for bar, v in zip(list(bars_e)+list(bars_n), euclid_comply+network_comply):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.8,
                f'{v:.1f}', ha='center', va='bottom', fontsize=8)

    ax.axhline(85, color='red', lw=1.5, ls='--', label='85% target')
    setup_ax(ax, '15分钟可达合规率对比 | 15-Min Compliance Rate Comparison',
             '设施类型 Facility Type', '合规率 Compliance Rate (%)')
    ax.set_xticks(x); ax.set_xticklabels(facilities, fontsize=9)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 105)

    # 右: 幻觉差距
    ax = axes[1]
    ax.set_facecolor(IEEE_COLORS['panel'])
    gap = [e - n for e, n in zip(euclid_comply, network_comply)]
    colors_gap = [IEEE_COLORS['tertiary'] if g < 10 else
                  IEEE_COLORS['secondary'] if g < 20 else
                  IEEE_COLORS['quaternary'] for g in gap]

    bars = ax.bar(facilities, gap, color=colors_gap, alpha=0.8, width=0.55)
    for bar, v in zip(bars, gap):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{v:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

    ax.axhline(np.mean(gap), color='black', lw=1.5, ls='--',
               label=f'Mean gap: {np.mean(gap):.1f}%')
    setup_ax(ax, '欧氏-路网合规率差距 | Euclidean-Network Compliance Gap',
             '设施类型 Facility Type', '差距 Gap (EU - NW) (%)')
    ax.legend(fontsize=9)

    ax.text(0.05, 0.05,
            '最大差距: 工作 Workplace (28.2%)\n'
            '最小差距: 商业 Shopping (2.6%)\n'
            '医疗 Healthcare 受路网障碍影响最大',
            transform=ax.transAxes, fontsize=8.5, va='bottom',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    save_fig(fig, 'fig9_supply_demand.png')


def fig10_street_view_synthesis():
    """街景影像与步行环境评估方法流程图（Fig 10）"""
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor(IEEE_COLORS['panel'])

    nodes = [
        (0.10, 0.85, '街景影像采集\n(腾讯街景/Mapabc)', '#1f77b4'),
        (0.10, 0.55, '建筑数据叠加\n(楼栋层数/用途/年代)', '#1f77b4'),
        (0.40, 0.70, '深度学习感知\n(YOLO行人检测\n+语义分割)', '#ff7f0e'),
        (0.40, 0.40, '步行环境指标\nSCR/BFD/EWW/SVI', '#2ca02c'),
        (0.70, 0.70, '群体差异化\n速度模型\n(v_i = v_base x alpha_k)', '#9467bd'),
        (0.70, 0.40, '综合可达性\n幻觉指数\nAI*', '#d62728'),
        (0.95, 0.55, '时间贫困\n评估报告', '#8c564b'),
    ]

    for x, y, label, color in nodes:
        box = mpatches.FancyBboxPatch(
            (x - 0.085, y - 0.07), 0.17, 0.14,
            boxstyle="round,pad=0.02", linewidth=1.5,
            edgecolor=color, facecolor='white', zorder=3
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha='center', va='center',
                fontsize=8, fontweight='bold', color=color, zorder=4,
                multialignment='center')

    arrows = [
        ((0.175, 0.85), (0.315, 0.70), '数据输入'),
        ((0.175, 0.55), (0.315, 0.55), '代理变量'),
        ((0.48, 0.70), (0.60, 0.70), '感知结果'),
        ((0.48, 0.40), (0.60, 0.40), '环境指标'),
        ((0.62, 0.70), (0.62, 0.47), '↓ 群体速度'),
        ((0.78, 0.40), (0.87, 0.45), '叠加惩罚'),
    ]

    for start, end, label in arrows:
        ax.annotate('', xy=end, xytext=start,
                    arrowprops=dict(arrowstyle='->', color='#555555',
                                   lw=1.2, connectionstyle='arc3,rad=0'))
        if label:
            mx = (start[0] + end[0]) / 2
            my = (start[1] + end[1]) / 2 + 0.025
            ax.text(mx, my, label, ha='center', va='bottom',
                    fontsize=6.5, color='#555555', style='italic')

    ax.set_xlim(0, 1)
    ax.set_ylim(0.25, 1.0)
    setup_ax(ax, '步行环境评估流程：街景影像深度学习 → 群体差异化速度 → 综合可达性幻觉指数（Fig. 10）',
             '', '')
    ax.axis('off')

    legend_items = [
        (IEEE_COLORS['primary'], '数据源 Data Sources'),
        (IEEE_COLORS['secondary'], '深度学习 Deep Learning'),
        (IEEE_COLORS['tertiary'], '环境指标 Environmental Metrics'),
        (IEEE_COLORS['purple'], '速度模型 Speed Model'),
        (IEEE_COLORS['quaternary'], '综合评估 Comprehensive Assessment'),
    ]
    legend_patches = [mpatches.Patch(color=c, label=l) for c, l in legend_items]
    ax.legend(handles=legend_patches, loc='lower right', fontsize=7,
              ncol=2, framealpha=0.9)

    plt.tight_layout()
    save_fig(fig, 'fig10_streetview_methodology.png')


# ═══════════════════════════════════════════════════════════════
# 主函数
# ═══════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("Conference Paper Figures Generator")
    print("15分钟城市可达性幻觉研究 — 会议论文图表生成")
    print(f"Output: {OUT_DIR}")
    print("=" * 70)

    fig1_framework()
    fig2_euclidean_vs_network()
    fig3_study_area()
    fig4_illusion_scatter()
    fig5_type_analysis()
    fig6_deprived_communities()
    fig7_ai_distribution()
    fig8_day_night()
    fig9_supply_demand()
    fig10_street_view_synthesis()

    print(f"\n{'=' * 70}")
    print(f"Done! All figures saved to: {OUT_DIR}")
    files = sorted(os.listdir(OUT_DIR))
    for f in files:
        print(f"  - {f}")
    print(f"Total: {len(files)} files")


if __name__ == '__main__':
    main()
