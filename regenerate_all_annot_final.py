# -*- coding: utf-8 -*-
"""
Regenerate all 294 annotated images with proper Chinese font rendering.
Includes Village (城中村) category with correct color scheme.
"""
import os
import sys
import io
import warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import font_manager

# ── Font ────────────────────────────────────────────────
ACTIVE_FONT = 'C:/Windows/Fonts/simhei.ttf'
if not os.path.exists(ACTIVE_FONT):
    ACTIVE_FONT = 'C:/Windows/Fonts/msyh.ttc'
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
print(f'Font: {ACTIVE_FONT}')

# ── Paths ────────────────────────────────────────────────
BASE     = r'E:\xicha gis 智能定位'
RAW_BASE = os.path.join(BASE, 'appendix-vlm', 'appendix_raw', 'appendix_raw')
ANNOT_DIR= os.path.join(BASE, 'appendix-vlm', 'appendix_annotated', 'appendix_annotated')

# ── Constants ──────────────────────────────────────────────
DIR_LABELS = {'N': '北', 'S': '南', 'E': '东', 'W': '西'}

SCHEMES = {
    'LowRise': {
        'header': '#1565C0', 'accent': '#1976D2',
        'header_text': '低密度建成区',
    },
    'MidRise': {
        'header': '#E65100', 'accent': '#F57C00',
        'header_text': '中密度建成区',
    },
    'OpenOther': {
        'header': '#2E7D32', 'accent': '#388E3C',
        'header_text': '开放其他',
    },
    'Village': {
        'header': '#4A148C', 'accent': '#6A1B9A',
        'header_text': '城中村区域',
    },
}

# ── Helper: draw one annotated image ─────────────────────
def draw_annot(raw_img_path, out_path, direction, region, scheme_key):
    scheme = SCHEMES.get(scheme_key, SCHEMES['OpenOther'])

    raw_img = Image.open(raw_img_path).convert('RGB')
    W, H = raw_img.size

    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor('white')
    ax.axis('off')
    ax.imshow(np.array(raw_img), aspect='auto')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    f_sm = font_manager.FontProperties(fname=ACTIVE_FONT, size=13)
    f_md = font_manager.FontProperties(fname=ACTIVE_FONT, size=14)
    f_lg = font_manager.FontProperties(fname=ACTIVE_FONT, size=16)

    hh = 0.10  # header height fraction

    # Header bar
    ax.add_patch(mpatches.Rectangle(
        (0, 1 - hh), 1, hh,
        transform=ax.transAxes, facecolor=scheme['header'],
        edgecolor='none', zorder=3
    ))

    # Direction badge (left)
    ax.text(0.035, 1 - hh / 2,
            DIR_LABELS.get(direction, direction),
            transform=ax.transAxes, fontproperties=f_lg,
            color='white', fontweight='bold',
            ha='center', va='center', zorder=4)

    # Region (center)
    ax.text(0.50, 1 - hh / 2,
            region,
            transform=ax.transAxes, fontproperties=f_sm,
            color='white',
            ha='center', va='center', zorder=4)

    # Obstacle type (right)
    ax.text(0.97, 1 - hh / 2,
            scheme['header_text'],
            transform=ax.transAxes, fontproperties=f_sm,
            color='white',
            ha='center', va='center', zorder=4)

    # Bottom label
    coord_str = os.path.basename(raw_img_path).replace('_2022.jpg', '')
    coord_str = '_'.join(coord_str.split('_')[:2])
    ax.text(0.5, 0.025,
            f'{coord_str}  {DIR_LABELS.get(direction, direction)}向',
            transform=ax.transAxes, fontproperties=f_sm,
            color='white', ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.2',
                      fc='#333333', ec='none', alpha=0.85),
            zorder=4)

    # Left strip
    ax.add_patch(mpatches.Rectangle(
        (0, 0.12), 0.014, 0.58,
        transform=ax.transAxes, facecolor=scheme['accent'],
        edgecolor='none', zorder=3, alpha=0.90
    ))

    plt.tight_layout(pad=0)

    # Save via PNG to avoid JPEG quality issues
    tmp_png = out_path.replace('.jpg', '_regen_tmp.png')
    fig.savefig(tmp_png, dpi=100, bbox_inches=None,
                facecolor='white', format='png')
    plt.close(fig)

    Image.open(tmp_png).convert('RGB').save(out_path, 'JPEG', quality=92)
    os.remove(tmp_png)

# ── Process Village category ────────────────────────────────
print('\n[1] Processing Village (城中村) images...')
village_root = os.path.join(RAW_BASE, 'Village')
count_village = 0
if os.path.exists(village_root):
    for coord_dir in os.listdir(village_root):
        vp = os.path.join(village_root, coord_dir)
        if not os.path.isdir(vp):
            continue
        for fname in os.listdir(vp):
            if not fname.endswith('.jpg'):
                continue
            parts = fname.replace('.jpg', '').split('_')
            if len(parts) < 4:
                continue
            direction = parts[2]
            out_fname = f'{parts[0]}_{parts[1]}_{direction}_{parts[3]}_annot.jpg'
            out_path = os.path.join(ANNOT_DIR, out_fname)
            draw_annot(
                os.path.join(vp, fname), out_path,
                direction, '城中村', 'Village'
            )
            count_village += 1
print(f'  Village done: {count_village} images')

# ── Process all other categories ──────────────────────────
print('[2] Processing building-area images...')
count_building = 0
annot_files = set(f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg'))

for root, dirs, files in os.walk(RAW_BASE):
    if os.path.basename(root) == 'Village':
        continue  # skip village
    if not files:
        continue
    jpg_files = [f for f in files if f.endswith('.jpg')]
    if not jpg_files:
        continue

    rel = os.path.relpath(root, RAW_BASE)
    parts = rel.split(os.sep)
    if len(parts) < 3:
        continue

    obstacle = parts[-2]  # e.g. "OpenOther-开放其他"
    coord    = parts[-1]  # e.g. "113.850064_22.566972"

    # Determine scheme
    if 'LowRise' in obstacle:
        scheme_key = 'LowRise'
    elif 'MidRise' in obstacle:
        scheme_key = 'MidRise'
    elif 'OpenOther' in obstacle:
        scheme_key = 'OpenOther'
    else:
        scheme_key = 'OpenOther'

    for fname in jpg_files:
        fparts = fname.replace('.jpg', '').split('_')
        if len(fparts) < 4:
            continue
        direction = fparts[2]
        year = fparts[3]
        out_fname = f'{fparts[0]}_{fparts[1]}_{direction}_{year}_annot.jpg'
        out_path = os.path.join(ANNOT_DIR, out_fname)

        raw_path = os.path.join(root, fname)
        draw_annot(raw_path, out_path, direction, '南山区', scheme_key)
        count_building += 1

print(f'  Building done: {count_building} images')

# ── Verify ──────────────────────────────────────────────
annot_count = len([f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg')])
print(f'\nTotal annotation files: {annot_count}')
print('All done!')
