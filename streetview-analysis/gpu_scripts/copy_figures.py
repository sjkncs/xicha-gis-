import os, shutil, sys
sys.stdout.reconfigure(encoding='utf-8')

src_dir = r'e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_v2_samples'
dst_dir = r'e:\xicha gis 智能定位\papers\conference-slides\会议论文\15min可达性幻觉\overleaf_paper\figures'

os.makedirs(dst_dir, exist_ok=True)

# Representative images for paper:
# 1. High obstacle (obs=100, many vehicles) -> 113.919728_22.531067_N_2022_annotated.jpg
# 2. Moderate obstacle (obs=56.6, one car) -> 113.904989_22.528524_E_2022_annotated.jpg
# 3. Low obstacle (obs=0, clear view) -> 113.895074_22.513113_E_2022_annotated.jpg

selections = [
    ('113.919728_22.531067_N_2022_annotated.jpg', 'fig_sim_high_obstacle.jpg'),
    ('113.904989_22.528524_E_2022_annotated.jpg', 'fig_sim_moderate_obstacle.jpg'),
    ('113.895074_22.513113_E_2022_annotated.jpg', 'fig_sim_low_obstacle.jpg'),
    ('113.884019_22.500940_N_2022_annotated.jpg', 'fig_sim_sample1.png'),
    ('113.904989_22.528524_E_2022_annotated.jpg', 'fig_sim_sample2.png'),
]

for src_fn, dst_fn in selections:
    src_path = os.path.join(src_dir, src_fn)
    dst_path = os.path.join(dst_dir, dst_fn)
    if os.path.exists(src_path):
        shutil.copy2(src_path, dst_path)
        size = os.path.getsize(dst_path) / 1024
        print(f"Copied: {dst_fn} ({size:.0f} KB)")
    else:
        print(f"NOT FOUND: {src_path}")

# Also copy some directional comparison images
for direction in ['N', 'S', 'E', 'W']:
    fn = f'113.896598_22.531469_{direction}_2022_annotated.jpg'
    src = os.path.join(src_dir, fn)
    dst = os.path.join(dst_dir, f'fig_sim_{direction}.jpg')
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied directional: {fn}")

print("\nAll done. Figures in:", dst_dir)
for f in sorted(os.listdir(dst_dir)):
    sz = os.path.getsize(os.path.join(dst_dir, f)) / 1024
    print(f"  {f} ({sz:.0f} KB)")
