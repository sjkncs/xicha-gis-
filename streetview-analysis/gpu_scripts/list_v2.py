import os, sys
sys.stdout.reconfigure(encoding='utf-8')
base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\sim_v2_samples"
files = sorted(os.listdir(base))
print(f"Total: {len(files)}")
for f in files:
    size = os.path.getsize(os.path.join(base, f)) / 1024
    # Extract coords from filename
    print(f"  {f} ({size:.0f}KB)")
