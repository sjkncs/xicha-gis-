# -*- coding: utf-8 -*-
"""
Regenerate all 294 annotated images with proper Chinese font rendering.
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

# ── Font setup ──────────────────────────────────────────────
FONT_PATH = 'C:/Windows/Fonts/simhei.ttf'
plt.rcParams['font.sans-serif'] = [
    'SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans'
]
plt.rcParams['axes.unicode_minus'] = False

yahei_path = 'C:/Windows/Fonts/msyh.ttc'
simhei_path = 'C:/Windows/Fonts/simhei.ttf'
ACTIVE_FONT = simhei_path if os.path.exists(simhei_path) else (
    yahei_path if os.path.exists(yahei_path) else None
)
print(f'Font: {ACTIVE_FONT}')

# ── Paths ──────────────────────────────────────────────────
BASE      = r'E:\xicha gis 智能定位'
RAW_BASE  = os.path.join(BASE, 'appendix-vlm', 'appendix_raw', 'appendix_raw')
ANNOT_DIR = os.path.join(BASE, 'appendix-vlm', 'appendix_annotated', 'appendix_annotated')

# ── Label maps ──────────────────────────────────────────────
DIR_LABELS = {'N': '北', 'S': '南', 'E': '东', 'W': '西'}

OBSTACLE_LABELS = {
    'LowRise-低密度': '低密度建成区',
    'MidRise-中密度': '中密度建成区',
    'OpenOther-开放其他': '开放其他',
}

# ── Build FULL coord → metadata mapping ─────────────────────
# Each raw coord folder has 4 direction images
# We need ALL 4 directions for each coordinate
coord_map = {}  # (coord_str, direction) -> metadata dict

for root, dirs, files in os.walk(RAW_BASE):
    if not files:
        continue
    jpg_files = [f for f in files if f.lower().endswith('.jpg')]
    if not jpg_files:
        continue

    rel = os.path.relpath(root, RAW_BASE)
    parts = rel.split(os.sep)
    if len(parts) < 3:
        continue

    # parts: [region, subregion, category, obstacle_type, coord]
    region   = parts[0]
    obstacle = parts[-2]  # e.g. "OpenOther-开放其他"
    coord    = parts[-1]  # e.g. "113.850064_22.566972"

    label_en = OBSTACLE_LABELS.get(obstacle, obstacle)

    for fname in jpg_files:
        # Parse: lng_lat_dir_year.jpg
        base = fname.replace('.jpg', '')
        fparts = base.split('_')
        if len(fparts) < 4:
            continue
        direction = fparts[2]  # N/S/E/W
        year = fparts[3]
        full_coord = fparts[0] + '_' + fparts[1]  # "113.850064_22.566972"

        key = (full_coord, direction)
        coord_map[key] = {
            'coord':    full_coord,
            'direction': direction,
            'year':     year,
            'obstacle': obstacle,
            'label':    label_en,
            'region':   region,
            'raw_dir':  root,
            'raw_file': os.path.join(root, fname),
        }

print(f'coord_map entries: {len(coord_map)}')

# ── Load all annotation filenames ────────────────────────────
annot_files = {}  # (coord, direction) -> fname
for fname in sorted(os.listdir(ANNOT_DIR)):
    if not fname.endswith('_annot.jpg'):
        continue
    base = fname.replace('_annot.jpg', '')
    parts = base.split('_')
    if len(parts) >= 4:
        coord = parts[0] + '_' + parts[1]
        direction = parts[2]
        annot_files[(coord, direction)] = fname

print(f'annot_files: {len(annot_files)}')

# Check overlap
missing = [k for k in annot_files if k not in coord_map]
print(f'Missing from coord_map: {len(missing)}')
if missing:
    for k in missing[:5]:
        print(f'  {k}: {annot_files[k]}')

# ── Color schemes for obstacle types ─────────────────────────
SCHEMES = {
    'LowRise-低密度': {
        'header': '#1565C0', 'accent': '#1976D2',
        'header_text': '低密度建成区',
    },
    'MidRise-中密度': {
        'header': '#E65100', 'accent': '#F57C00',
        'header_text': '中密度建成区',
    },
    'OpenOther-开放其他': {
        'header': '#2E7D32', 'accent': '#388E3C',
        'header_text': '开放其他',
    },
}

# ── Regenerate function ─────────────────────────────────────
def regenerate(key, annot_fname):
    meta = coord_map[key]
    raw_img_path = meta['raw_file']
    direction   = meta['direction']
    region      = meta['region']
    obstacle    = meta['obstacle']
    label       = meta['label']
    coord_str   = meta['coord']
    scheme      = SCHEMES.get(obstacle, SCHEMES['OpenOther-开放其他'])

    # Load raw image
    try:
        raw_img = Image.open(raw_img_path).convert('RGB')
        W, H = raw_img.size
    except Exception as e:
        return False, f'Cannot open: {e}'

    # Draw
    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    fig.patch.set_facecolor('white')
    ax.axis('off')
    ax.imshow(np.array(raw_img), aspect='auto')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    font_sm = font_manager.FontProperties(fname=ACTIVE_FONT, size=13)
    font_md = font_manager.FontProperties(fname=ACTIVE_FONT, size=14)
    font_lg = font_manager.FontProperties(fname=ACTIVE_FONT, size=16)

    # Header bar
    header_h = 0.10
    rect = mpatches.Rectangle(
        (0, 1 - header_h), 1, header_h,
        transform=ax.transAxes, facecolor=scheme['header'],
        edgecolor='none', zorder=3
    )
    ax.add_patch(rect)

    # Direction badge (left)
    ax.text(0.035, 1 - header_h / 2,
            DIR_LABELS.get(direction, direction),
            transform=ax.transAxes,
            fontproperties=font_lg, color='white', fontweight='bold',
            ha='center', va='center', zorder=4)

    # Region (center)
    ax.text(0.50, 1 - header_h / 2,
            region,
            transform=ax.transAxes,
            fontproperties=font_sm, color='white',
            ha='center', va='center', zorder=4)

    # Obstacle type (right)
    ax.text(0.97, 1 - header_h / 2,
            scheme['header_text'],
            transform=ax.transAxes,
            fontproperties=font_sm, color='white',
            ha='center', va='center', zorder=4)

    # Bottom coordinate label
    ax.text(0.5, 0.025,
            f'{coord_str}  {DIR_LABELS.get(direction, direction)}向',
            transform=ax.transAxes,
            fontproperties=font_sm, color='white',
            ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.2',
                      fc='#333333', ec='none', alpha=0.85),
            zorder=4)

    # Left color strip
    side_rect = mpatches.Rectangle(
        (0, 0.12), 0.014, 0.58,
        transform=ax.transAxes, facecolor=scheme['accent'],
        edgecolor='none', zorder=3, alpha=0.90
    )
    ax.add_patch(side_rect)

    plt.tight_layout(pad=0)

    out_path = os.path.join(ANNOT_DIR, annot_fname)
    # Save as PNG for quality (then we'll use it as-is)
    out_png = out_path.replace('.jpg', '_new.png')
    fig.savefig(out_png, dpi=100, bbox_inches=None,
                facecolor='white', format='png')
    plt.close(fig)

    # Convert PNG -> JPEG quality via PIL
    img_out = Image.open(out_png).convert('RGB')
    img_out.save(out_path, 'JPEG', quality=92)
    os.remove(out_png)

    return True, out_path

# ── Run ───────────────────────────────────────────────────
print(f'\nRegenerating {len(annot_files)} images...')
ok_count = 0
fail_count = 0
errors = []

for i, ((coord, direction), fname) in enumerate(annot_files.items()):
    key = (coord, direction)
    if key not in coord_map:
        fail_count += 1
        errors.append((key, 'no coord_map entry'))
        continue

    ok, msg = regenerate(key, fname)
    if ok:
        ok_count += 1
        if ok_count % 50 == 0:
            print(f'  [{ok_count}/{len(annot_files)}] done...')
    else:
        fail_count += 1
        errors.append((key, msg))
        if fail_count <= 5:
            print(f'  FAIL {coord}/{direction}: {msg}')

print(f'\nResult: {ok_count} OK, {fail_count} FAILED')
if errors:
    print(f'Errors ({len(errors)}):')
    for k, e in errors[:10]:
        print(f'  {k}: {e}')
