import os, sys
sys.stdout.reconfigure(encoding='utf-8')
base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

for d in ["sim_samples", "sim_v2_samples"]:
    path = os.path.join(base, d)
    if os.path.exists(path):
        files = sorted(os.listdir(path))
        print(f"\n{d}: {len(files)} files")
        for f in files:
            size = os.path.getsize(os.path.join(path, f)) / 1024
            print(f"  {f} ({size:.0f}KB)")
    else:
        print(f"\n{d}: NOT EXISTS")
