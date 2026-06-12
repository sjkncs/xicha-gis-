# Debug: check raw folder coordinate format vs annotation filename format
import os

RAW_BASE  = r'E:\xicha gis 智能定位\appendix-vlm\appendix_raw\appendix_raw'
ANNOT_DIR = r'E:\xicha gis 智能定位\appendix-vlm\appendix_annotated\appendix_annotated'

# Collect ALL raw coords
raw_coords = set()
for root, dirs, files in os.walk(RAW_BASE):
    if files:
        rel = os.path.relpath(root, RAW_BASE)
        parts = rel.split(os.sep)
        coord = parts[-1]  # last dir = coordinate
        for f in files:
            if f.endswith('.jpg'):
                fname_parts = f.replace('.jpg', '').split('_')
                if len(fname_parts) >= 2:
                    raw_coord = fname_parts[0] + '_' + fname_parts[1]
                    raw_coords.add(raw_coord)

print(f'Raw coords count: {len(raw_coords)}')
print(f'Sample raw coords:')
for c in sorted(list(raw_coords))[:5]:
    print(f'  "{c}"')

# Collect ALL annot coords
annot_coords = {}
for fname in os.listdir(ANNOT_DIR):
    if fname.endswith('_annot.jpg'):
        base = fname.replace('_annot.jpg', '')
        parts = base.split('_')
        if len(parts) >= 4:
            coord = parts[0] + '_' + parts[1]
            direction = parts[2]
            annot_coords[(coord, direction)] = fname

print(f'\nAnnot entries: {len(annot_coords)}')
print(f'Sample annot coords:')
for c in sorted(list(annot_coords.keys()))[:5]:
    print(f'  "{c}"')

# Check overlap
matched = set()
unmatched = set()
for key in annot_coords:
    coord, direction = key
    if coord in raw_coords:
        matched.add(key)
    else:
        unmatched.add(key)

print(f'\nMatched: {len(matched)}')
print(f'Unmatched: {len(unmatched)}')
if unmatched:
    print('First 10 unmatched:')
    for k in list(unmatched)[:10]:
        print(f'  {k}')

# Try with more flexible matching
print('\n--- Trying float-based matching ---')
# Parse all annot coords as floats
annot_coords_float = {}
for (coord, direction), fname in annot_coords.items():
    parts = coord.split('_')
    lng = float(parts[0])
    lat = float(parts[1])
    annot_coords_float[(lng, lat, direction)] = fname

raw_coords_float = {}
for rc in raw_coords:
    parts = rc.split('_')
    lng = float(parts[0])
    lat = float(parts[1])
    raw_coords_float[(lng, lat)] = rc

matched2 = 0
unmatched2 = []
for (lng, lat, direction), fname in annot_coords_float.items():
    raw_key = (lng, lat)
    if raw_key in raw_coords_float:
        matched2 += 1
    else:
        unmatched2.append((lng, lat, direction, fname))

print(f'Float-matched: {matched2}')
print(f'Float-unmatched: {len(unmatched2)}')
if unmatched2:
    print('First 10 float-unmatched:')
    for item in unmatched2[:10]:
        print(f'  lng={item[0]}, lat={item[1]}, dir={item[2]}')
        print(f'  fname={item[3]}')
        # Check nearby
        nearby = [(k, v) for k, v in raw_coords_float.items() if abs(k[0]-item[0])<0.01 and abs(k[1]-item[1])<0.01]
        if nearby:
            print(f'  Nearby raw: {nearby[:3]}')
