# -*- coding: utf-8 -*-
"""Handle the 4 Village annotation images separately."""
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

ACTIVE_FONT = 'C:/Windows/Fonts/simhei.ttf'
ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
RAW_VILLAGE = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw\Village'

DIR_LABELS = {'N': '北', 'S': '南', 'E': '东', 'W': '西'}

# Village has structure: Village/{coord}/4张.jpg
for coord_dir in os.listdir(RAW_VILLAGE):
    coord_path = os.path.join(RAW_VILLAGE, coord_dir)
    if not os.path.isdir(coord_path):
        continue

    for fname in os.listdir(coord_path):
        if not fname.endswith('.jpg'):
            continue

        # Parse: lng_lat_dir_year.jpg
        base = fname.replace('.jpg', '')
        parts = base.split('_')
        if len(parts) < 4:
            continue
        lng = parts[0]
        lat = parts[1]
        direction = parts[2]
        year = parts[3]
        coord_str = f'{lng}_{lat}'

        raw_path = os.path.join(coord_path, fname)
        annot_fname = f'{lng}_{lat}_{direction}_{year}_annot.jpg'
        out_path = os.path.join(ANNOT_DIR, annot_fname)

        print(f'Processing: {annot_fname}')

        # Load raw image
        raw_img = Image.open(raw_path).convert('RGB')
        W, H = raw_img.size

        # Draw annotation
        fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
        fig.patch.set_facecolor('white')
        ax.axis('off')
        ax.imshow(np.array(raw_img), aspect='auto')
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        font_sm = font_manager.FontProperties(fname=ACTIVE_FONT, size=13)
        font_md = font_manager.FontProperties(fname=ACTIVE_FONT, size=14)
        font_lg = font_manager.FontProperties(fname=ACTIVE_FONT, size=16)

        # Header: special Village style (dark purple)
        scheme_header = '#4A148C'
        scheme_accent = '#6A1B9A'
        header_text   = '城中村'

        header_h = 0.10
        rect = mpatches.Rectangle(
            (0, 1 - header_h), 1, header_h,
            transform=ax.transAxes,
            facecolor=scheme_header, edgecolor='none', zorder=3
        )
        ax.add_patch(rect)

        ax.text(0.035, 1 - header_h / 2,
                DIR_LABELS.get(direction, direction),
                transform=ax.transAxes,
                fontproperties=font_lg, color='white', fontweight='bold',
                ha='center', va='center', zorder=4)

        ax.text(0.50, 1 - header_h / 2,
                '城中村',
                transform=ax.transAxes,
                fontproperties=font_sm, color='white',
                ha='center', va='center', zorder=4)

        ax.text(0.97, 1 - header_h / 2,
                '城中村区域',
                transform=ax.transAxes,
                fontproperties=font_sm, color='white',
                ha='center', va='center', zorder=4)

        # Bottom label
        ax.text(0.5, 0.025,
                f'{coord_str}  {DIR_LABELS.get(direction, direction)}向',
                transform=ax.transAxes,
                fontproperties=font_sm, color='white',
                ha='center', va='center',
                bbox=dict(boxstyle='round,pad=0.2',
                          fc='#333333', ec='none', alpha=0.85),
                zorder=4)

        # Left strip
        side_rect = mpatches.Rectangle(
            (0, 0.12), 0.014, 0.58,
            transform=ax.transAxes,
            facecolor=scheme_accent, edgecolor='none', zorder=3, alpha=0.90
        )
        ax.add_patch(side_rect)

        plt.tight_layout(pad=0)

        # Save as PNG then JPEG
        tmp_png = out_path.replace('.jpg', '_tmp.png')
        fig.savefig(tmp_png, dpi=100, bbox_inches=None,
                    facecolor='white', format='png')
        plt.close(fig)

        img_out = Image.open(tmp_png).convert('RGB')
        img_out.save(out_path, 'JPEG', quality=92)
        os.remove(tmp_png)
        print(f'  -> Saved: {annot_fname}')

print('\nVillage annotations done!')
