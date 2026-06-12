# -*- coding: utf-8 -*-
"""Regenerate all 294 annotated images with proper Chinese font rendering.
The obstacle types are encoded in the appendix_raw folder structure.
We recover the obstacle info by mapping folder names to known categories."""
import os
import sys
import io
import warnings
warnings.filterwarnings('ignore')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Font setup - try multiple Chinese fonts
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Verify SimHei is available
import matplotlib.font_manager as fm
available_fonts = [f.name for f in fm.fontManager.ttflist]
chinese_fonts = [f for f in available_fonts if any(c in f.lower() for c in ['simhei', 'microsoft', 'noto', 'wqy', 'source han'])]
print('Chinese fonts available:', chinese_fonts[:10])

# Check the raw folder structure to recover folder names
RAW_BASE = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw'
ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
OUT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
os.makedirs(OUT_DIR, exist_ok=True)

# Walk the raw directory to build a coordinate->obstacle mapping
# Format: appendix_raw/{区域}/{子区域}/{障碍物分类}/{障碍物类型}/{coord}/4张.jpg
# We'll use the immediate subfolder name as the obstacle type

coord_to_obstacle = {}  # coord -> obstacle_type string
obstacle_folders = set()

for root, dirs, files in os.walk(RAW_BASE):
    # The immediate subfolder of the coordinate folder contains the images
    rel = os.path.relpath(root, RAW_BASE)
    parts = rel.split(os.sep)
    if len(parts) >= 4 and len(files) == 4:
        # parts: [region, subregion, category, obstacle_type, coord]
        # coord is the last part
        coord = parts[-1]
        obstacle_type = parts[-2]  # e.g. "OpenOther-various" or "车辆乱停"
        region = parts[0]

        # Decode folder names properly
        try:
            coord_decoded = coord  # Already decoded by OS
            obstacle_decoded = obstacle_type
            region_decoded = region
        except:
            coord_decoded = coord
            obstacle_decoded = obstacle_type
            region_decoded = region

        coord_to_obstacle[coord] = {
            'obstacle_type': obstacle_decoded,
            'region': region_decoded,
            'full_path': root
        }
        obstacle_folders.add(obstacle_decoded)

print(f'Found {len(coord_to_obstacle)} coordinate points')
print(f'Obstacle types found: {obstacle_folders}')
print(f'Sample entries:')
for i, (k, v) in enumerate(list(coord_to_obstacle.items())[:5]):
    print(f'  {k}: {v}')
