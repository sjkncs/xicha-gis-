# Analyze all 294 annotation files to understand their sources
import os

ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'
RAW_BASE  = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw'
BASE     = r'E:\xicha gis 智能定位'

# Get all annotation files
annot_files = sorted([f for f in os.listdir(ANNOT_DIR) if f.endswith('_annot.jpg')])
print(f'Total annotation files: {len(annot_files)}')

# Parse each annotation file
entries = []
for fname in annot_files:
    base = fname.replace('_annot.jpg', '')
    parts = base.split('_')
    if len(parts) >= 4:
        lng = parts[0]
        lat = parts[1]
        direction = parts[2]
        year = parts[3]
        coord = f'{lng}_{lat}'
        entries.append({
            'fname': fname, 'coord': coord,
            'direction': direction, 'year': year,
            'lng': lng, 'lat': lat
        })

# Check which ones exist in raw folder
found_in_raw = 0
not_in_raw = []
raw_coords = set()
for root, dirs, files in os.walk(RAW_BASE):
    if files:
        # Get coord from path
        rel = os.path.relpath(root, RAW_BASE)
        for f in files:
            if f.endswith('.jpg'):
                parts2 = f.replace('.jpg', '').split('_')
                if len(parts2) >= 3:
                    raw_coords.add(parts2[0] + '_' + parts2[1])

print(f'Raw coords: {len(raw_coords)}')

found_entries = []
for e in entries:
    if e['coord'] in raw_coords:
        found_in_raw += 1
        found_entries.append(e)
    else:
        not_in_raw.append(e)

print(f'Found in raw: {found_in_raw}')
print(f'NOT in raw: {len(not_in_raw)}')

# Show first 10 not-in-raw entries
print('\nFirst 10 NOT in raw:')
for e in not_in_raw[:10]:
    print(f'  {e["coord"]} {e["direction"]} -> {e["fname"]}')

# Check: are there other image source directories?
print('\nSearching for other image sources...')
other_dirs = []
for root, dirs, files in os.walk(os.path.join(BASE, 'appendix-vlm')):
    for f in files:
        if f.endswith('.jpg') and '_annot' not in f:
            rel = os.path.relpath(root, os.path.join(BASE, 'appendix-vlm'))
            other_dirs.append(rel)
            break

from collections import Counter
dir_counts = Counter(other_dirs)
for d, cnt in dir_counts.most_common(10):
    print(f'  {d}: {cnt} images')

# Check if any directory named 'gsv' or 'streetview' or ' Tencent' etc
print('\nAll subdirs of appendix-vlm:')
for root, dirs, files in os.walk(os.path.join(BASE, 'appendix-vlm')):
    level = root.replace(os.path.join(BASE, 'appendix-vlm'), '').count(os.sep)
    indent = '  ' * level
    if level <= 2:
        print(f'{indent}{os.path.basename(root)}/ ({len(files)} files)')
