# Check the Village folder specifically
import os

RAW_BASE = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw'
ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'

# Look at Village folder specifically
for root, dirs, files in os.walk(RAW_BASE):
    rel = os.path.relpath(root, RAW_BASE)
    if 'Village' in rel or 'village' in rel.lower():
        print(f'DIR: {rel}')
        print(f'  Files: {files[:5]}')
        for f in files:
            if f.endswith('.jpg'):
                print(f'  -> {f}')

# Also check for the specific coord 113.9263685_22.5129279
print('\nSearching for 113.9263685_22.5129279...')
for root, dirs, files in os.walk(RAW_BASE):
    if '113.9263685_22.5129279' in root or any('113.9263685_22.5129279' in f for f in files):
        print(f'Found: {root}')
        print(f'  Files: {files}')

# Check the existing Village annotation images
print('\nVillage-related annotation files:')
for f in sorted(os.listdir(ANNOT_DIR)):
    if '9263685' in f or '5129279' in f:
        print(f'  {f}')
