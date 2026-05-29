#!/usr/bin/env python3
"""Download Nanshan District FCN heatmaps + generate comprehensive local charts"""
import paramiko, os, json, sys, numpy as np

sys.stdout.reconfigure(encoding='utf-8')

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER   = "root"
SSH_PASS   = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp/streetview_analysis"
LOCAL_BASE  = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

with open(f"{LOCAL_BASE}/all_results_fixed.json", "r", encoding="utf-8") as f:
    data = json.load(f)

nanshan = [r for r in data if "/南山区/" in r["image"]]
nanshan.sort(key=lambda x: x["accessibility_score"])

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)
sftp = ssh.open_sftp()

# Download FCN heatmaps - pick high/mid/low samples from Nanshan
def extract_coords_from_filename(fn):
    # e.g. 南山区_南头_未知社区_OpenOther-开放其他_113.917632_22.559302_113.917632_22.559302_E_2022_fcn.jpg
    parts = fn.split('_')
    for i, p in enumerate(parts):
        if p.startswith('113.'):
            return p, parts[i+1] if i+1 < len(parts) and parts[i+1] in ['N','E','S','W'] else 'X'
    return None, 'X'

def extract_coords_from_path(path):
    fn = os.path.basename(path)
    return extract_coords_from_filename(fn)

# High(>=60), Mid(30-60), Low(<=10) - each 2 samples
high = [r for r in nanshan if r["accessibility_score"] >= 60]
mid  = [r for r in nanshan if 30 <= r["accessibility_score"] < 60]
low  = [r for r in nanshan if r["accessibility_score"] <= 10]

samples = (high[-2:][::-1] + mid[len(mid)//2-1:len(mid)//2+1] + low[:2])
print(f"Downloading {len(samples)} FCN heatmap samples...")

hm_dir = f"{LOCAL_BASE}/heatmaps_nanshan"
os.makedirs(hm_dir, exist_ok=True)

# Build filename matching patterns
# FCN heatmaps: 南山区_街道_社区_类型_坐标_坐标_方向_2022_fcn.jpg
target_coords = set()
for r in samples:
    fn = r["image"].split("/")[-1]
    for part in fn.replace('.jpg','').split('_'):
        if part.startswith('113.'):
            target_coords.add(part)
            break

print(f"Target coords: {sorted(target_coords)}")

# List available FCN heatmaps
stdin, stdout, stderr = ssh.exec_command(f"find {REMOTE_BASE}/output/heatmaps -maxdepth 1 -name '*.jpg' | sort")
all_fcn = [l.strip() for l in stdout.read().decode('utf-8', errors='replace').split('\n') if l.strip() and '南山区' in l]
print(f"Found {len(all_fcn)} Nanshan FCN heatmaps on server")

# Download matching ones
downloaded = 0
for rp in all_fcn:
    fn = os.path.basename(rp)
    coords, direction = extract_coords_from_filename(fn)
    if coords in target_coords:
        # find matching score
        matched_score = 0
        for r in samples:
            if coords in r["image"]:
                matched_score = int(r["accessibility_score"])
                break
        bn = fn.replace("_fcn.jpg", "_score" + str(matched_score) + ".jpg")
        lp = os.path.join(hm_dir, bn)
        if not os.path.exists(lp):
            try:
                sftp.get(rp, lp)
                sz = os.path.getsize(lp)
                print(f"  [OK] {bn} ({sz} bytes)")
                downloaded += 1
            except Exception as e:
                print(f"  [FAIL] {fn}: {e}")
        else:
            print(f"  [EXISTS] {bn}")

print(f"\nDownloaded {downloaded} heatmaps")

# Also download a few YOLO heatmaps if available
stdin, stdout, stderr = ssh.exec_command(f"find {REMOTE_BASE}/output/heatmaps/yolo_blocked_only/ground_view -name '*.png' | head -5")
yolo_pngs = [l.strip() for l in stdout.read().decode('utf-8', errors='replace').split('\n') if l.strip()]
yolo_dir = f"{LOCAL_BASE}/heatmaps_yolo"
os.makedirs(yolo_dir, exist_ok=True)
for rp in yolo_pngs[:5]:
    bn = os.path.basename(rp)
    lp = os.path.join(yolo_dir, bn)
    if not os.path.exists(lp):
        try:
            sftp.get(rp, lp)
            sz = os.path.getsize(lp)
            print(f"  [YOLO] {bn} ({sz} bytes)")
        except Exception as e:
            print(f"  [YOLO FAIL] {bn}: {e}")

sftp.close()
ssh.close()

# ===== Generate charts =====
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    chart_dir = f"{LOCAL_BASE}/charts"
    os.makedirs(chart_dir, exist_ok=True)

    # 1. Category bar chart
    cats = {}
    for r in data:
        for cat, cnt in r["categories"].items():
            cats[cat] = cats.get(cat, 0) + cnt
    sorted_cats = sorted(cats.items(), key=lambda x: -x[1])
    names = [c[0] for c in sorted_cats]
    vals  = [c[1] for c in sorted_cats]
    colors = ['#e74c3c' if '汽车' in n or '货车' in n else
              '#3498db' if '行人' in n else
              '#f39c12' if '摩托' in n else
              '#27ae60' if '公交' in n or '自行' in n else
              '#9b59b6' for n in names]

    fig, ax = plt.subplots(figsize=(12, 6))
    bars = ax.barh(names[::-1], vals[::-1], color=colors[::-1], edgecolor='white')
    for bar, v in zip(bars, vals[::-1]):
        ax.text(v + max(vals)*0.01, bar.get_y() + bar.get_height()/2,
                f' {v} ({v/sum(vals)*100:.1f}%)', va='center', fontsize=11)
    ax.set_xlabel('Detection Count', fontsize=13)
    ax.set_title('Obstacle Category Distribution (All Districts, YOLO11x)', fontsize=14, fontweight='bold')
    ax.set_xlim(0, max(vals)*1.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    p1 = f"{chart_dir}/category_distribution.png"
    plt.savefig(p1, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"\nChart 1: {p1} ({os.path.getsize(p1)} bytes)")

    # 2. Score histogram
    all_scores = [r["accessibility_score"] for r in data]
    ns_scores  = [r["accessibility_score"] for r in nanshan]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    bins = [0, 10, 20, 40, 60, 80, 100]
    labels = ['0-10\nSmooth', '10-20\nFair', '20-40\nNormal', '40-60\nDifficult', '60-80\nHard', '80-100\nSevere']
    bar_colors = ['#27ae60', '#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#c0392b']

    n_all, _, patches_all = ax1.hist(all_scores, bins=bins, edgecolor='white', linewidth=0.8)
    for patch, color in zip(patches_all, bar_colors):
        patch.set_facecolor(color)
    for i, (count, lo) in enumerate(zip(n_all, bins)):
        if count > 0:
            ax1.text((lo + bins[i+1])/2, count + 0.5, f'{int(count)}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax1.set_xlabel('Accessibility Obstacle Score', fontsize=12)
    ax1.set_ylabel('Number of Images', fontsize=12)
    ax1.set_title(f'All Districts (N={len(all_scores)}, Mean={np.mean(all_scores):.1f})', fontsize=13, fontweight='bold')
    ax1.set_xticks([5, 15, 30, 50, 70, 90])
    ax1.set_xticklabels(labels, fontsize=9)

    n_ns, _, patches_ns = ax2.hist(ns_scores, bins=bins, edgecolor='white', linewidth=0.8)
    for patch, color in zip(patches_ns, bar_colors):
        patch.set_facecolor(color)
    for i, (count, lo) in enumerate(zip(n_ns, bins)):
        if count > 0:
            ax2.text((lo + bins[i+1])/2, count + 0.3, f'{int(count)}', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax2.set_xlabel('Accessibility Obstacle Score', fontsize=12)
    ax2.set_ylabel('Number of Images', fontsize=12)
    ax2.set_title(f'Nanshan District (N={len(ns_scores)}, Mean={np.mean(ns_scores):.1f})', fontsize=13, fontweight='bold')
    ax2.set_xticks([5, 15, 30, 50, 70, 90])
    ax2.set_xticklabels(labels, fontsize=9)

    plt.suptitle('Accessibility Obstacle Score Distribution (higher = more barriers)', fontsize=15, fontweight='bold', y=1.02)
    plt.tight_layout()
    p2 = f"{chart_dir}/score_distribution.png"
    plt.savefig(p2, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Chart 2: {p2} ({os.path.getsize(p2)} bytes)")

    # 3. District comparison
    fig, ax = plt.subplots(figsize=(12, 7))
    districts = {}
    for r in data:
        parts = r["image"].split("/")
        district = parts[5] if len(parts) >= 6 else "Unknown"
        if district not in districts:
            districts[district] = {"scores": [], "cats": {}}
        districts[district]["scores"].append(r["accessibility_score"])
        for cat, cnt in r["categories"].items():
            districts[district]["cats"][cat] = districts[district]["cats"].get(cat, 0) + cnt

    names_d  = []
    means_d   = []
    stds_d   = []
    counts_d = []
    for d, info in sorted(districts.items(), key=lambda x: -np.mean(x[1]["scores"])):
        names_d.append(d)
        means_d.append(np.mean(info["scores"]))
        stds_d.append(np.std(info["scores"]))
        counts_d.append(len(info["scores"]))

    bar_colors_d = ['#e74c3c' if m >= 25 else '#f39c12' if m >= 15 else '#27ae60' for m in means_d]
    x = np.arange(len(names_d))
    bars = ax.bar(x, means_d, yerr=stds_d, capsize=6, color=bar_colors_d,
                  edgecolor='white', linewidth=0.8, alpha=0.85, error_kw={'linewidth': 1.5})
    for i, (bar, m, c) in enumerate(zip(bars, means_d, counts_d)):
        err = stds_d[i]
        ax.text(bar.get_x() + bar.get_width()/2, m + err + 2,
                f'{m:.1f}\n(n={c})', ha='center', va='bottom', fontsize=11, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(names_d, fontsize=12)
    ax.set_ylabel('Mean Obstacle Score', fontsize=13)
    ax.set_title('District Comparison: Mean Accessibility Obstacle Score\n(higher = more barriers)', fontsize=14, fontweight='bold')
    ax.set_ylim(0, max(m + s for m, s in zip(means_d, stds_d)) * 1.25)
    ax.axhline(np.mean(all_scores), color='#555', linestyle='--', linewidth=2, label=f'Overall Mean: {np.mean(all_scores):.1f}')
    ax.legend(fontsize=11)

    green_patch = mpatches.Patch(color='#27ae60', label='Low (<15): Good')
    orange_patch = mpatches.Patch(color='#f39c12', label='Medium (15-25): Moderate')
    red_patch = mpatches.Patch(color='#e74c3c', label='High (>=25): Difficult')
    ax.legend(handles=[green_patch, orange_patch, red_patch, plt.Line2D([0],[0],color='#555',linestyle='--',linewidth=2,label=f'Overall: {np.mean(all_scores):.1f}')], fontsize=10)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    plt.tight_layout()
    p3 = f"{chart_dir}/district_comparison.png"
    plt.savefig(p3, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Chart 3: {p3} ({os.path.getsize(p3)} bytes)")

    print(f"\nAll charts saved to: {chart_dir}")
except Exception as e:
    print(f"Chart error: {e}")
    import traceback; traceback.print_exc()

print(f"\nHeatmap samples: {len(os.listdir(hm_dir))} files")
print(f"YOLO heatmaps: {len(os.listdir(yolo_dir))} files")
