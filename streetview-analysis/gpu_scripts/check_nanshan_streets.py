#!/usr/bin/env python3
"""Check Nanshan street breakdown from server heatmap filenames"""
import os, sys, json, paramiko
from collections import defaultdict
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER = "root"
SSH_PASS = "roBbKv+ed3Vm"
BASE = "/root/autodl-tmp/streetview_analysis"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)

# Get unique Nanshan heatmap filenames
stdin, stdout, stderr = ssh.exec_command(
    f"find {BASE}/output/heatmaps -maxdepth 1 -name '南山区*' | head -20"
)
files = [l.strip() for l in stdout.read().decode('utf-8', errors='replace').split('\n') if l.strip()]
print("Sample Nanshan heatmap names:")
for f in files[:10]:
    print(f"  {os.path.basename(f)}")

ssh.close()

# Parse street from filename pattern: 南山区_街道_社区_OpenOther-开放其他_坐标_坐标_方向_2022_fcn.jpg
street_map = defaultdict(lambda: {"count": 0, "coords": set()})

# We have all_results_fixed.json - parse street from there
with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
print(f"\nNanshan images: {len(nanshan)}")

# Parse street from full path
# /root/autodl-tmp/streetview_analysis/images/南山区/{STREET}/{COMMUNITY}/.../{coords}/{file}.jpg
street_data = defaultdict(lambda: {"imgs": [], "scores": [], "cats": defaultdict(int), "coords": set()})
for r in nanshan:
    parts = r["image"].split("/")
    # parts: ['', 'root', 'autodl-tmp', 'streetview_analysis', 'images', '南山区', '街道', '社区', 'OpenOther-开放其他', 'coords', 'filename.jpg']
    if len(parts) >= 7:
        street = parts[6]
    else:
        street = "未知街道"
    street_data[street]["imgs"].append(parts[-1] if parts else "")
    street_data[street]["scores"].append(r["accessibility_score"])
    street_data[street]["coords"].add(r["coords"])
    for cat, cnt in r["categories"].items():
        street_data[street]["cats"][cat] += cnt

print("\nStreet breakdown:")
for street, info in sorted(street_data.items(), key=lambda x: -len(x[1]["scores"])):
    import numpy as np
    scores = info["scores"]
    mean_s = np.mean(scores)
    cats_str = ", ".join([f"{k}({v})" for k,v in sorted(info["cats"].items(), key=lambda x:-x[1])])
    print(f"  {street}: n={len(scores)}, coords={len(info['coords'])}, mean={mean_s:.1f}, max={max(scores):.0f}")
    print(f"    cats: {cats_str}")
