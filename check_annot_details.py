# Check annotation image details
import os
from PIL import Image

ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
files = [f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg')]
print('Need to regenerate:', len(files), 'annotated images')

img = Image.open(os.path.join(ANNOT_DIR, files[0]))
print('Annot image size:', img.size, 'mode:', img.mode)

# Check raw directory structure for the same file
raw_img = files[0].replace('_annot.jpg', '.jpg')
print('Looking for raw image:', raw_img)

raw_base = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw'
found = False
for root, dirs, files2 in os.walk(raw_base):
    if raw_img in files2:
        raw_path = os.path.join(root, raw_img)
        print('Raw found:', raw_path)
        img2 = Image.open(raw_path)
        print('Raw size:', img2.size, 'mode:', img2.mode)
        found = True
        break
if not found:
    print('Raw image NOT found')

# Show folder names in appendix_raw (these are the obstacle types)
print('\nappendix_raw folder structure:')
for root, dirs, files2 in os.walk(raw_base):
    # Print directory hierarchy
    rel = os.path.relpath(root, raw_base)
    if dirs:
        for d in dirs:
            print(f'  {rel}/{d}')
    if found:
        break
