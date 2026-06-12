# Analyze existing annotated images to understand annotation format
import os
import numpy as np
from PIL import Image

ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
OUT_DIR = r'E:\xicha gis 智能定位\projects\15min-urban-accessibility\paper\figures'

files = sorted([f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg')])
print(f'Analyzing {len(files)} annotated images...')

# Analyze colors used in annotations
color_samples = []
for fname in files[:20]:
    img = Image.open(os.path.join(ANNOT_DIR, fname)).convert('RGB')
    arr = np.array(img)

    # Look at top strip (where labels usually are)
    top_strip = arr[:60, :]
    # Get unique colors in the top area
    pixels = top_strip.reshape(-1, 3)
    # Quantize to reduce noise
    quantized = (pixels // 32) * 32
    unique = np.unique(quantized, axis=0)

    for color in unique:
        if not (color[0] == color[1] == color[2]):  # Not grayscale
            if color[0] > 180 and color[1] < 100 and color[2] < 100:  # Red
                color_samples.append(('RED', color, fname))
            elif color[0] < 100 and color[1] > 150 and color[2] < 100:  # Green
                color_samples.append(('GREEN', color, fname))
            elif color[0] > 200 and color[1] > 150 and color[2] < 100:  # Yellow
                color_samples.append(('YELLOW', color, fname))
            elif color[0] > 100 and color[1] < 100 and color[2] > 150:  # Purple
                color_samples.append(('PURPLE', color, fname))

# Deduplicate
seen = set()
for cat, color, fname in color_samples:
    key = (cat, tuple(color))
    if key not in seen:
        seen.add(key)
        print(f'  {cat}: RGB{tuple(color)} in {fname}')

# Analyze existing generate_streetview_figures_v2.py to see what obstacle types exist
print('\nSearching for obstacle type definitions in existing scripts...')
for script in ['generate_streetview_figures_v2.py', 'generate_streetview_figures.py']:
    path = os.path.join(r'E:\xicha gis 智能定位', script)
    if os.path.exists(path):
        with open(path, encoding='utf-8', errors='ignore') as f:
            content = f.read()
        for line in content.split('\n'):
            if any(k in line for k in ['obstacle', '障碍', '遮挡', '类型', 'category', 'class']):
                print(f'  [{script}] {line.strip()[:100]}')
