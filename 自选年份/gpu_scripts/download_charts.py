#!/usr/bin/env python3
"""Download YOLO obstacle heatmap samples + generate local charts"""
import paramiko, os, json, sys, numpy as np

sys.stdout.reconfigure(encoding='utf-8')

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER   = "root"
SSH_PASS   = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp/streetview_analysis"
LOCAL_BASE  = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

# Load results
with open(f"{LOCAL_BASE}/all_results_fixed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
nanshan.sort(key=lambda x: x["accessibility_score"])

# High/mid/low
high = nanshan[-3:][::-1]   # top 3
mid  = nanshan[len(nanshan)//2-1:len(nanshan)//2+2]
low  = nanshan[:3]

samples_to_fetch = (high + mid + low)
print(f"Fetching {len(samples_to_fetch)} heatmap samples...")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)
sftp = ssh.open_sftp()

# Find heatmap files by listing ground_view dir
stdin, stdout, stderr = ssh.exec_command(
    f"find {REMOTE_BASE}/output/heatmaps/yolo_blocked_only/ground_view -name '*.png' | head -50"
)
all_png = [l.strip() for l in stdout.read().decode('utf-8', errors='replace').split('\n') if l.strip()]
print(f"Found {len(all_png)} heatmap PNGs on server")

# Build map: coords+dir -> remote_path
def png_key(path):
    fn = os.path.basename(path)  # e.g. 南山区_街道_社区_xxx_coord_E_2022_yolo_blocked.png
    # Extract coords and direction
    parts = fn.split('_')
    coords = None
    direction = None
    for i, p in enumerate(parts):
        if p.startswith('113.') and '_' in p:
            coords = p
            if i+1 < len(parts) and parts[i+1] in ['N','E','S','W']:
                direction = parts[i+1]
            break
    return (coords, direction)

png_map = {png_key(p): p for p in all_png}

# Also check main BASE dir for any stray PNGs
stdin, stdout, stderr = ssh.exec_command(f"ls {REMOTE_BASE}/*.png {REMOTE_BASE}/*.jpg 2>/dev/null")
extra_files = [l.strip() for l in stdout.read().decode('utf-8', errors='replace').split('\n') if l.strip()]
print(f"Extra files in base: {extra_files}")

hm_dir = f"{LOCAL_BASE}/heatmaps"
os.makedirs(hm_dir, exist_ok=True)

def download_png(remote_path, local_name):
    lp = os.path.join(hm_dir, local_name)
    if os.path.exists(lp) and os.path.getsize(lp) > 1000:
        print(f"  [exists] {local_name}")
        return
    try:
        sftp.get(remote_path, lp)
        sz = os.path.getsize(lp)
        print(f"  [OK] {local_name} ({sz} bytes)")
    except Exception as e:
        print(f"  [FAIL] {local_name}: {e}")

# Download by coords matching
for r in samples_to_fetch:
    fn = r["image"].split("/")[-1]
    coords_raw = fn.replace('.jpg','')
    # Try to match via the PNG map
    # PNG naming: 南山区_街道_社区_coords_E_2022_yolo_blocked.png
    # We need to match by coords
    for key, rpath in png_map.items():
        coords, direction = key
        if coords and coords in coords_raw and direction:
            bn = f"{coords}_{direction}_score{int(r['accessibility_score'])}.png"
            download_png(rpath, bn)
            break

sftp.close()
ssh.close()

# Generate local charts using matplotlib
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    all_scores = [r["accessibility_score"] for r in data]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Chart 1: Category bar chart
    cats = {}
    for r in data:
        for cat, cnt in r["categories"].items():
            cats[cat] = cats.get(cat, 0) + cnt
    if cats:
        sorted_cats = sorted(cats.items(), key=lambda x: -x[1])
        names = [c[0] for c in sorted_cats]
        vals  = [c[1] for c in sorted_cats]
        colors = ['#e74c3c' if '汽车' in n or '货车' in n or '摩托' in n else
                  '#3498db' if '行人' in n else
                  '#2ecc71' if '自行车' in n else
                  '#f39c12' if '公交' in n else
                  '#9b59b6' for n in names]
        ax = axes[0]
        bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1])
        for bar, v in zip(bars, vals[::-1]):
            ax.text(v + max(vals)*0.01, bar.get_y() + bar.get_height()/2,
                    f' {v}', va='center', fontsize=10)
        ax.set_xlabel('Count', fontsize=12)
        ax.set_title('Obstacle Category Distribution (All Districts)', fontsize=13)
        ax.set_xlim(0, max(vals)*1.15)

    # Chart 2: Score histogram
    ax = axes[1]
    bins = [0, 10, 20, 40, 60, 80, 100]
    labels = ['0-10\nSmooth', '10-20\nFair', '20-40\nNormal', '40-60\nDifficult', '60-80\nHard', '80-100\nSevere']
    n_hist, edges, patches = ax.hist(all_scores, bins=bins, edgecolor='white', linewidth=0.8)
    bar_colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b']
    for patch, color in zip(patches, bar_colors):
        patch.set_facecolor(color)
    for i, (count, edge) in enumerate(zip(n_hist, edges)):
        ax.text((edge + (edges[i+1] if i+1 < len(edges) else 100))/2, count + 0.5,
                f'{int(count)}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_xlabel('Accessibility Obstacle Score', fontsize=12)
    ax.set_ylabel('Number of Images', fontsize=12)
    ax.set_title(f'Score Distribution (N={len(all_scores)}, Mean={np.mean(all_scores):.1f})', fontsize=13)
    ax.set_xticks([5, 15, 30, 50, 70, 90])
    ax.set_xticklabels(labels, fontsize=9)

    plt.tight_layout()
    chart_path = f"{LOCAL_BASE}/charts/yolo_obstacle_overview.png"
    os.makedirs(os.path.dirname(chart_path), exist_ok=True)
    plt.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    sz = os.path.getsize(chart_path)
    print(f"\nChart saved: {chart_path} ({sz} bytes)")

    # Chart 3: District comparison
    fig2, ax2 = plt.subplots(figsize=(12, 6))
    districts = {}
    for r in data:
        parts = r["image"].split("/")
        district = parts[5] if len(parts) >= 6 else "Unknown"
        if district not in districts:
            districts[district] = []
        districts[district].append(r["accessibility_score"])

    names = []
    means = []
    stds  = []
    counts = []
    for d, scores in sorted(districts.items(), key=lambda x: -np.mean(x[1])):
        names.append(d)
        means.append(np.mean(scores))
        stds.append(np.std(scores))
        counts.append(len(scores))

    colors = ['#e74c3c' if m >= 25 else '#f39c12' if m >= 15 else '#2ecc71' for m in means]
    x = np.arange(len(names))
    bars = ax2.bar(x, means, yerr=stds, capsize=5, color=colors, edgecolor='white', linewidth=0.8, alpha=0.85)
    for i, (bar, m, c) in enumerate(zip(bars, means, counts)):
        err_val = stds[i] if i < len(stds) else 0
        ax2.text(bar.get_x() + bar.get_width()/2, m + err_val + 2,
                 f'{m:.1f}\n(n={c})', ha='center', va='bottom', fontsize=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(names, fontsize=11)
    ax2.set_ylabel('Mean Obstacle Score', fontsize=12)
    ax2.set_title('District Comparison: Mean Accessibility Obstacle Score (higher=more obstacles)', fontsize=13)
    ax2.set_ylim(0, max(m + s for m, s in zip(means, stds)) * 1.25)
    ax2.axhline(np.mean(all_scores), color='gray', linestyle='--', linewidth=1.5, label=f'Overall Mean: {np.mean(all_scores):.1f}')
    ax2.legend()

    chart_path2 = f"{LOCAL_BASE}/charts/yolo_district_comparison.png"
    plt.savefig(chart_path2, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    sz2 = os.path.getsize(chart_path2)
    print(f"Chart saved: {chart_path2} ({sz2} bytes)")

except Exception as e:
    print(f"Chart generation error: {e}")
    import traceback; traceback.print_exc()

print(f"\nHeatmap samples: {len(os.listdir(hm_dir))} files")
