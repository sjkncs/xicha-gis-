# -*- coding: utf-8 -*-
import os, glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from PIL import Image
import warnings
warnings.filterwarnings('ignore')

# 中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

BASE = os.path.join('E:', os.sep, 'xicha gis \u667a\u80fd\u5b9a\u4f4d')
ANNOT_DIR = os.path.join(BASE, 'appendix-vlm', 'appendix_annotated', 'appendix_annotated')
RAW_DIR = os.path.join(BASE, 'appendix-vlm', 'appendix_raw', 'appendix_raw')
OUT_DIR = os.path.join(BASE, 'projects', '15min-urban-accessibility', 'paper', 'figures')

# 方向映射
DIR_MAP = {'N': '\u5317', 'S': '\u5357', 'E': '\u4e1c', 'W': '\u897f'}

# 从标注目录找到所有可用文件，建立「坐标_方向 -> 文件路径」的映射
annot_files = {}
for fname in os.listdir(ANNOT_DIR):
    if fname.endswith('_annot.jpg'):
        # 格式: 经度_纬度_方向_年份_annot.jpg
        parts = fname.replace('_annot.jpg', '').split('_')
        if len(parts) >= 3:
            coord = parts[0] + '_' + parts[1]
            direction = parts[2]
            annot_files[(coord, direction)] = os.path.join(ANNOT_DIR, fname)

print('\u6807\u6ce8\u6587\u4ef6\u6570:', len(annot_files))

# 根据坐标找原始图的函数
# 原始图目录结构: appendix_raw/appendix_raw/{分类}/{子分类}/{障碍类型}/{坐标点}/4张.jpg
def find_raw_images(coord, direction):
    """根据坐标和方向，在raw目录中找4张原始图"""
    coord_short = coord  # e.g. "113.924917_22.513049"
    for root, dirs, files in os.walk(RAW_DIR):
        coord_dirs = [d for d in dirs if coord in d]
        for cd in coord_dirs:
            full_dir = os.path.join(root, cd)
            imgs = [f for f in os.listdir(full_dir) if f.lower().endswith(('.jpg', '.png'))]
            if imgs:
                return [os.path.join(full_dir, f) for f in imgs]
    return []

# 选择代表性样本：尽量覆盖不同区域+不同障碍类型
candidates = [
    ('113.924917_22.513049', 'E', '\u79d1\u6280\u56ed\u5546\u4e1a\u8857-\u4e1c\u5411'),
    ('113.924917_22.513049', 'W', '\u79d1\u6280\u56ed\u5546\u4e1a\u8857-\u897f\u5411'),
    ('113.914454_22.492678', 'E', '\u57ce\u4e2d\u6751-\u4e1c\u5411\u5df7\u9053'),
    ('113.914454_22.492678', 'W', '\u57ce\u4e2d\u6751-\u897f\u5411\u5df7\u9053'),
    ('113.995109_22.593694', 'E', '\u86c7\u53e3\u8857\u533a-\u4e1c\u5411'),
    ('113.995109_22.593694', 'S', '\u86c7\u53e3\u8857\u533a-\u5357\u5411'),
    ('113.933918_22.542275', 'N', '\u9ad8\u5c42\u4f4f\u5b85\u533a-\u5317\u5411'),
    ('113.933918_22.542275', 'S', '\u9ad8\u5c42\u4f4f\u5b85\u533a-\u5357\u5411'),
    ('114.004033_22.644601', 'N', '\u5317\u90e8\u57ce\u4e2d\u6751-\u5317\u5411'),
    ('114.004033_22.644601', 'W', '\u5317\u90e8\u57ce\u4e2d\u6751-\u897f\u5411'),
    ('113.986221_22.538660', 'E', '\u5feb\u901f\u8def\u5468\u8fb9-\u4e1c\u5411'),
    ('113.986221_22.538660', 'W', '\u5feb\u901f\u8def\u5468\u8fb9-\u897f\u5411'),
]

# 匹配找到的标注图
selected = []
for coord, direction, label in candidates:
    key = (coord, direction)
    if key in annot_files:
        raw_imgs = find_raw_images(coord, direction)
        selected.append((annot_files[key], label, direction, raw_imgs))
        print('OK: %s %s -> %s' % (coord, direction, label))

print('\u627e\u5230 %d \u5f20\u6807\u6ce8\u56fe' % len(selected))

# ============================================================
# 图一：纯标注图拼接（3行4列）
# ============================================================
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
        img_path, label, direction, raw_imgs = selected[idx]
        try:
            img = Image.open(img_path).convert('RGB')
            ax.imshow(np.array(img), aspect='auto')

            # \u65b9\u5411\u6807\u7b7e\uff08\u53f3\u4e0a\u89d2\uff09
            ax.text(0.97, 0.97, DIR_MAP.get(direction, direction),
                    transform=ax.transAxes,
                    fontsize=7, fontweight='bold', color='white',
                    ha='right', va='top',
                    bbox=dict(boxstyle='round,pad=0.2', fc='#333333', ec='none', alpha=0.8))

            # \u5e95\u90e8\u56fe\u4f8b\u6807\u7b7e
            ax.text(0.5, 0.02, label,
                    transform=ax.transAxes,
                    fontsize=5.5, color='#222222',
                    ha='center', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='#AAAAAA', alpha=0.9, lw=0.5))
        except Exception as e:
            ax.text(0.5, 0.5, '\u52a0\u8f7d\u5931\u8d25',
                    transform=ax.transAxes, fontsize=7,
                    ha='center', va='center', color='gray')
    else:
        ax.text(0.5, 0.5, '(\u65e0\u6570\u636e)',
                transform=ax.transAxes, fontsize=7,
                ha='center', va='center', color='lightgray')

# \u603b\u6807\u9898
fig.suptitle('\u56fe10-a  \u6df1\u5733\u5e02\u5178\u578b\u5efa\u6210\u73af\u5883\u8857\u666f\u969c\u788e\u7269\u6807\u6ce8\u6837\u672c\uff08n=12\uff09',
              fontsize=11, fontweight='bold', y=0.98, color='#1a1a1a')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
out_A = os.path.join(OUT_DIR, 'fig_sv_obstacle_mosaic.png')
fig.savefig(out_A, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print('\u65b9\u6848A\u4fdd\u5b58:', out_A)

# ============================================================
# 图二：原图 vs 标注对照（2行6对）
# ============================================================
fig2, axes2 = plt.subplots(2, 12, figsize=(18, 6))
fig2.patch.set_facecolor('white')

# \u6bcf\u5bf9\u8868\u793a\uff1a\u5de6=\u539f\u59cb\u56fe \u53f3=\u6807\u6ce8\u56fe
for row in range(2):
    for pair_idx in range(6):
        idx = row * 6 + pair_idx
        if idx >= len(selected):
            axes2[row, pair_idx * 2].axis('off')
            axes2[row, pair_idx * 2 + 1].axis('off')
            continue

        img_path, label, direction, raw_imgs = selected[idx]

        # \u5de6\uff1a\u539f\u59cb\u56fe
        ax_raw = axes2[row, pair_idx * 2]
        ax_raw.set_facecolor('#F0F0F0')
        ax_raw.set_xticks([])
        ax_raw.set_yticks([])
        for spine in ax_raw.spines.values():
            spine.set_edgecolor('#DDDDDD')
            spine.set_linewidth(0.3)

        loaded = False
        if raw_imgs:
            for rp in raw_imgs:
                try:
                    img_r = Image.open(rp).convert('RGB')
                    ax_raw.imshow(np.array(img_r), aspect='auto')
                    loaded = True
                    break
                except:
                    pass
        if not loaded:
            ax_raw.text(0.5, 0.5, '\u539f\u56fe',
                         transform=ax_raw.transAxes, fontsize=5,
                         ha='center', va='center', color='#BBBBBB', style='italic')

        # \u53f3\uff1a\u6807\u6ce8\u56fe
        ax_ann = axes2[row, pair_idx * 2 + 1]
        ax_ann.set_facecolor('#F0F0F0')
        ax_ann.set_xticks([])
        ax_ann.set_yticks([])
        for spine in ax_ann.spines.values():
            spine.set_edgecolor('#DDDDDD')
            spine.set_linewidth(0.3)
        try:
            img_a = Image.open(img_path).convert('RGB')
            ax_ann.imshow(np.array(img_a), aspect='auto')
        except:
            ax_ann.text(0.5, 0.5, '\u6807\u6ce8\u56fe',
                         transform=ax_ann.transAxes, fontsize=5,
                         ha='center', va='center', color='#BBBBBB', style='italic')

        # \u9876\u90e8\u65b9\u5411\u6807\u9898
        if row == 0:
            ax_raw.set_title(DIR_MAP.get(direction, direction) + '\u5411', fontsize=6, pad=2, color='#444444')
            ax_ann.set_title(DIR_MAP.get(direction, direction) + '\u5411', fontsize=6, pad=2, color='#444444')

        # \u5e95\u90e8\u6807\u7b7e
        if row == 1:
            for ax_tmp in [ax_raw, ax_ann]:
                ax_tmp.text(0.5, 0.02, label,
                            transform=ax_tmp.transAxes,
                            fontsize=4.5, color='#333333',
                            ha='center', va='bottom',
                            bbox=dict(boxstyle='round,pad=0.1', fc='white', ec='#CCC', alpha=0.85, lw=0.3))

# \u5217\u6807\u9898
fig2.text(0.5, 0.02, '<-- \u539f\u59cb\u56fe        \u6807\u6ce8\u56fe -->',
          ha='center', fontsize=7, color='#666666', style='italic')

fig2.suptitle('\u56fe10-b  \u5178\u578b\u5efa\u6210\u73af\u5883\u8857\u666f\uff1a\u539f\u56fe\u4e0e\u969c\u788e\u7269\u6807\u6ce8\u5bf9\u7167',
              fontsize=10, fontweight='bold', y=0.98, color='#1a1a1a')

plt.tight_layout(rect=[0, 0.03, 1, 0.95])
out_B = os.path.join(OUT_DIR, 'fig_sv_before_after_mosaic.png')
fig2.savefig(out_B, dpi=300, bbox_inches='tight', facecolor='white')
plt.close()
print('\u65b9\u6848B\u4fdd\u5b58:', out_B)

print('\u5b8c\u6210!')
