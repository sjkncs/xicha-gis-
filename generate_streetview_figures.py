# -*- coding: utf-8 -*-
"""
生成街景标注图拼接大图 (Figure X - Street View Obstacle Annotations)
IEEE双栏投稿格式，白底，适配报告文档
从294张标注图中精选12张，组成3行4列mosaic
"""
import os, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

BASE = r'E:\xicha gis 智能定位'
ANNOT_DIR = os.path.join(BASE, 'appendix-vlm', 'appendix_annotated', 'appendix_annotated')
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')

# 选择代表性样本：尽量覆盖不同区域+不同障碍类型
# 命名格式: 经度_纬度_方向_年份_annot.jpg
candidates = [
    # 南山区科技园/商业核心
    ('113.924917_22.513049', 'E', '科技园商业街-东向'),
    ('113.924917_22.513049', 'W', '科技园商业街-西向'),
    # 城中村样本（密集巷道）
    ('113.914454_22.492678', 'E', '城中村-东向巷道'),
    ('113.914454_22.492678', 'W', '城中村-西向巷道'),
    # 蛇口/海岸区
    ('113.995109_22.593694', 'E', '蛇口街区-东向'),
    ('113.995109_22.593694', 'S', '蛇口街区-南向'),
    # 高密度建成区
    ('113.933918_22.542275', 'N', '高层住宅区-北向'),
    ('113.933918_22.542275', 'S', '高层住宅区-南向'),
    # 北部城中村带
    ('114.004033_22.644601', 'N', '北部城中村-北向'),
    ('114.004033_22.644601', 'W', '北部城中村-西向'),
    # 特殊障碍区
    ('113.986221_22.538660', 'E', '快速路周边-东向'),
    ('113.986221_22.538660', 'W', '快速路周边-西向'),
]

# 查找存在的文件
selected = []
for base_name, direction, label in candidates:
    for fname in os.listdir(ANNOT_DIR):
        if fname.startswith(base_name) and f'_{direction}_' in fname and fname.endswith('_annot.jpg'):
            full_path = os.path.join(ANNOT_DIR, fname)
            selected.append((full_path, label, direction))
            break

print(f'找到 {len(selected)} 张标注图')

# 同时找对应原始图（有对比效果）
raw_streetview_dir = os.path.join(BASE, '备选图像', 'raw_streetview')
raw_pairs = {}
for base_name, direction, label in candidates:
    for fname in os.listdir(ANNOT_DIR):
        if fname.startswith(base_name) and f'_{direction}_' in fname and fname.endswith('_annot.jpg'):
            raw_name = fname.replace('_annot.jpg', '.jpg')
            for root, dirs, files in os.walk(raw_streetview_dir):
                if raw_name in files:
                    raw_pairs[base_name + '_' + direction] = os.path.join(root, raw_name)
                    break

# ===== 生成图件 =====
# 方案A：纯标注图拼接（3行4列）
fig, axes = plt.subplots(3, 4, figsize=(14, 10.5))
fig.patch.set_facecolor('white')

n_rows, n_cols = 3, 4
total = n_rows * n_cols

for idx in range(total):
    row = idx // n_cols
    col = idx % n_cols
    ax = axes[row, col]
    ax.set_facecolor('#F8F9FA')
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor('#CCCCCC')
        spine.set_linewidth(0.5)

    if idx < len(selected):
        img_path, label, direction = selected[idx]
        try:
            img = Image.open(img_path).convert('RGB')
            img_array = np.array(img)
            ax.imshow(img_array, aspect='auto')

            # 方向标签（右上角）
            dir_map = {'N': '北', 'S': '南', 'E': '东', 'W': '西'}
            ax.text(0.97, 0.97, dir_map.get(direction, direction),
                    transform=ax.transAxes,
                    fontsize=7, fontweight='bold', color='white',
                    ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.2', fc='#333333', ec='none', alpha=0.8))

            # 底部图例标签
            ax.text(0.5, 0.02, label,
                    transform=ax.transAxes,
                    fontsize=5.5, color='#333333',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='#AAAAAA', alpha=0.9, lw=0.5))
        except Exception as e:
            ax.text(0.5, 0.5, f'加载失败\n{e}',
                    transform=ax.transAxes, fontsize=6,
                    ha='center', va='center', color='gray')
    else:
        ax.text(0.5, 0.5, '(无数据)',
                transform=ax.transAxes, fontsize=7,
                ha='center', va='center', color='lightgray')

# 总标题
fig.suptitle('图X  深圳市典型建成环境街景障碍物标注样本（n=12）',
              fontsize=11, fontweight='bold', y=0.98, color='#1a1a1a',
              fontfamily='SimHei')

# 添加图例
legend_elements = [
    mpatches.Patch(facecolor='#F8F9FA', edgecolor='#CCCCCC', label='图(a) 典型障碍物标注样本（4方向×3研究分区）'),
]
fig.legend(handles=legend_elements, loc='lower center',
           ncol=1, fontsize=7, frameon=True,
           bbox_to_anchor=(0.5, 0.01), handlelength=1.5, handleheight=1.0,
           edgecolor='#CCCCCC')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
out_path_A = os.path.join(OUT_DIR, 'fig_sv_obstacle_mosaic.png')
fig.savefig(out_path_A, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f'方案A保存: {out_path_A}')

# 方案B：标注+原始对照拼接（2行12列 = 6+6对照）
# 每行6对：原图 vs 标注
fig2, axes2 = plt.subplots(2, 12, figsize=(18, 6))
fig2.patch.set_facecolor('white')

for row in range(2):
    for col_pair in range(6):
        idx = row * 6 + col_pair
        if idx >= len(selected):
            axes2[row, col_pair * 2].axis('off')
            axes2[row, col_pair * 2 + 1].axis('off')
            continue

        img_path, label, direction = selected[idx]
        # 找原始图
        base_name = os.path.basename(img_path).split('_annot.jpg')[0]
        raw_path = None
        for root, dirs, files in os.walk(raw_streetview_dir):
            for f in files:
                if base_name + '.jpg' == f:
                    raw_path = os.path.join(root, f)
                    break

        # 左：原始
        ax_raw = axes2[row, col_pair * 2]
        ax_raw.set_facecolor('#F5F5F5')
        ax_raw.set_xticks([])
        ax_raw.set_yticks([])
        for spine in ax_raw.spines.values():
            spine.set_edgecolor('#DDDDDD')
            spine.set_linewidth(0.3)
        try:
            img = Image.open(img_path.replace('_annot.jpg', '.jpg').replace('_annot', '')).convert('RGB')
            # Try to find raw image without _annot suffix
            raw_img_path = None
            search_base = os.path.dirname(img_path)
            basename_no_ext = os.path.basename(img_path).replace('_annot.jpg', '')
            for f in os.listdir(search_base):
                if f.startswith(basename_no_ext) and not '_annot' in f and f.endswith('.jpg'):
                    raw_img_path = os.path.join(search_base, f)
                    break
            if raw_img_path and os.path.exists(raw_img_path):
                raw_img = Image.open(raw_img_path).convert('RGB')
                ax_raw.imshow(np.array(raw_img), aspect='auto')
        except:
            ax_raw.text(0.5, 0.5, '原图', transform=ax_raw.transAxes,
                       fontsize=5, ha='center', va='center', color='gray')

        # 右：标注
        ax_ann = axes2[row, col_pair * 2 + 1]
        ax_ann.set_facecolor('#F5F5F5')
        ax_ann.set_xticks([])
        ax_ann.set_yticks([])
        for spine in ax_ann.spines.values():
            spine.set_edgecolor('#DDDDDD')
            spine.set_linewidth(0.3)
        try:
            img = Image.open(img_path).convert('RGB')
            ax_ann.imshow(np.array(img), aspect='auto')
        except:
            ax_ann.text(0.5, 0.5, '标注图', transform=ax_ann.transAxes,
                       fontsize=5, ha='center', va='center', color='gray')

        # 列标签（只在第一行显示方向）
        if row == 0:
            dir_map = {'N': '北', 'S': '南', 'E': '东', 'W': '西'}
            label_text = f"{dir_map.get(direction, direction)}向"
            ax_raw.set_title(label_text, fontsize=5.5, pad=2, color='#444444')
            ax_ann.set_title(label_text, fontsize=5.5, pad=2, color='#444444')

# 添加列标题行标签
for ax_row, row_label in zip(axes2[0], ['原图↓  标注↑'] * 6):
    pass

fig2.text(0.5, 0.01, '← 原图        标注图 →', ha='center', fontsize=6,
          color='#666666', style='italic')

fig2.suptitle('图X  典型建成环境街景：原图与障碍物标注对照',
              fontsize=10, fontweight='bold', y=0.98, color='#1a1a1a',
              fontfamily='SimHei')

plt.tight_layout(rect=[0, 0.02, 1, 0.95])
out_path_B = os.path.join(OUT_DIR, 'fig_sv_before_after_mosaic.png')
fig2.savefig(out_path_B, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print(f'方案B保存: {out_path_B}')

print('Done!')
