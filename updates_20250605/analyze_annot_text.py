# Analyze existing annotated images to recover text labels
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
files = sorted([f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg')])

# Try to read text from images using a simple approach
# Check if any non-standard font was used by looking at pixel patterns

# Load a font to understand what characters look like
yahei = 'C:/Windows/Fonts/msyh.ttc'
if os.path.exists(yahei):
    font = ImageFont.truetype(yahei, 20)
    print('YaHei font available')
else:
    print('YaHei not found at:', yahei)

# Check what fonts exist for common Chinese
for font_path in [
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simsun.ttc',
]:
    print(f'{font_path}: exists={os.path.exists(font_path)}')

# Let's look at specific annotated images and try to match text against known strings
# Known obstacle text candidates:
known_texts = [
    '障碍物检测', '遮挡', '骑门廊', '商贩', '低密度', '中密度',
    '开放其他', '低密度建成区', '中密度建成区',
    'OpenOther', 'LowRise', 'MidRise', '未知社区'
]

# Check what text appears in the first few annotated images
for fname in files[:5]:
    img = Image.open(os.path.join(ANNOT_DIR, fname)).convert('RGB')
    arr = np.array(img)

    # Get top 20 rows where labels usually appear
    top = arr[:25, :]

    # Check if it's mostly non-white (label area)
    non_white = (top < 200).any(axis=2).sum()
    print(f'{fname}: top label area non-white pixels={non_white}')

    # Sample some rows for color coding
    for row in [5, 10, 15, 20]:
        for col in [50, 100, 150, 200]:
            r, g, b = arr[row, col]
            if not (r > 200 and g > 200 and b > 200):
                print(f'  row={row} col={col}: RGB({r},{g},{b})')
