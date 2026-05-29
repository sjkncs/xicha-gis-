import os, glob, json
res = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"
ann = os.path.join(res, "annotated_images")
pngs = sorted(glob.glob(os.path.join(ann, "*.png")))
print(f"Total: {len(pngs)} annotated images")
for p in pngs:
    size = os.path.getsize(p) / 1024
    print(f"  {os.path.basename(p)} ({size:.0f}KB)")

# Also check the new sim images
sim = os.path.join(res, "sim_results.json")
if os.path.exists(sim):
    with open(sim, encoding="utf-8") as f:
        data = json.load(f)
    print(f"\nsim_results.json: {len(data)} entries")
    for r in data[:3]:
        print(f"  {os.path.basename(r.get('annotated',''))} obs={r.get('obstacle_score','?')} pass={r.get('passability','?')}")

# Check tex file
tex = os.path.join(res, "nanshan_accessibility_analysis.tex")
print(f"\nLaTeX file: {'EXISTS' if os.path.exists(tex) else 'MISSING'}")
if os.path.exists(tex):
    print(f"  Size: {os.path.getsize(tex)} bytes")
