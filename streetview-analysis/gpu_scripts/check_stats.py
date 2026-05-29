import json

base = 'e:/xicha gis 智能定位/自选年份'
with open(f'{base}/all_sim_results.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

sorted_data = sorted(data, key=lambda x: x['obs_score'])

print('--- Top 3 HIGHEST obstacles (actual filenames) ---')
for r in sorted_data[-3:]:
    print(f'  obs={r["obs_score"]}, fn={r["image"]}, dir={r["direction"]}, coords={r["coords"]}')

print('\n--- Top 3 LOWEST obstacles (actual filenames) ---')
for r in sorted_data[:3]:
    print(f'  obs={r["obs_score"]}, fn={r["image"]}, dir={r["direction"]}, coords={r["coords"]}')

# Find moderate: closest to obs_score ~55-60 (middle of range)
target_mod = 55.0
moderate_img = min(data, key=lambda x: abs(x['obs_score'] - target_mod))
print(f'\n--- Moderate (~55-60): ---')
print(f'  obs={moderate_img["obs_score"]}, fn={moderate_img["image"]}, dir={moderate_img["direction"]}, coords={moderate_img["coords"]}')

# Also try obs around 50
for target in [50, 45, 55]:
    img = min(data, key=lambda x: abs(x['obs_score'] - target))
    print(f'  obs~{target}: {img["obs_score"]}, fn={img["image"]}, dir={img["direction"]}')

# Also show what the old representative images are
old_reps = {
    'high': 'pano_1139425_2249304_N.jpg',
    'moderate': 'pano_1139427_2249232_E.jpg',
    'low': 'pano_1139388_2249104_E.jpg'
}
for cat, fn in old_reps.items():
    for r in data:
        if r['image'] == fn:
            print(f'\nOld {cat} rep: {fn} -> obs={r["obs_score"]}, pass={r["passability"]}, dir={r["direction"]}')
