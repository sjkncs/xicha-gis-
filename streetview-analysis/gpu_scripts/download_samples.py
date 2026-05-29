#!/usr/bin/env python3
import paramiko, os, json

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER   = "root"
SSH_PASS   = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp/streetview_analysis"
LOCAL_BASE  = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results"

with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\results\all_results_fixed.json","r",encoding="utf-8") as f:
    data = json.load(f)

# 找南山区高中低评分的图片
nanshan = [r for r in data if "/南山区/" in r["image"]]
nanshan.sort(key=lambda x: x["accessibility_score"])

# 高(>=60)、中(30-60)、低(<=10)各选几个
high = [r for r in nanshan if r["accessibility_score"] >= 60]
mid  = [r for r in nanshan if 30 <= r["accessibility_score"] < 60]
low  = [r for r in nanshan if r["accessibility_score"] <= 10]

def extract_coords(img):
    # /root/autodl-tmp/.../images/TYPE/COORDS/file.jpg
    parts = img.split("/")
    return parts[-2] if len(parts) >= 2 else ""

def extract_direction(img):
    # filename like 113.xxx_22.xxx_N_2022.jpg
    fn = img.split("/")[-1]
    for d in ["_N_","_E_","_S_","_W_"]:
        if d in fn:
            return d[1]  # N/E/S/W
    return "X"

print(f"南山区: {len(nanshan)} 张 | 高分: {len(high)} | 中分: {len(mid)} | 低分: {len(low)}")

samples = []
for r in (high[:4] + mid[::max(1,len(mid)//4)][:4] + low[:4]):
    fn = r["image"].split("/")[-1]
    direction = extract_direction(r["image"])
    coords = extract_coords(r["image"])
    samples.append((coords, direction, fn, r["accessibility_score"], r["total_obstacles"], r["categories"]))

# 按评分排序
samples.sort(key=lambda x: x[3], reverse=True)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)
sftp = ssh.open_sftp()

# 下载server上的图表
remote_charts = [
    f"{REMOTE_BASE}/category_bar_street_view.png",
    f"{REMOTE_BASE}/score_dist_street_view.png",
]
local_charts = f"{LOCAL_BASE}/charts"
os.makedirs(local_charts, exist_ok=True)
for rc in remote_charts:
    bn = os.path.basename(rc)
    lc = os.path.join(local_charts, bn)
    if not os.path.exists(lc) or os.path.getsize(lc) == 0:
        try:
            sftp.get(rc, lc)
            sz = os.path.getsize(lc)
            print(f"Downloaded chart: {bn} ({sz} bytes)")
        except Exception as e:
            print(f"Chart not found: {rc} - {e}")
    else:
        print(f"Chart exists: {bn}")

# 下载viz样本 (从Nanshan子目录)
nanshan_viz_dir = f"{REMOTE_BASE}/viz_samples_nanshan"
os.makedirs(nanshan_viz_dir, exist_ok=True)

for coords, direction, fn, score, n_obs, cats in samples:
    # viz图片在 detect_final.py 运行的当前目录，即 REMOTE_BASE 下
    # viz格式: filename.jpg -> filename.png
    # 先尝试南山区子目录
    possible_paths = [
        f"{REMOTE_BASE}/viz_samples_nanshan/{coords}_{direction}/{fn.replace('.jpg','.png')}",
        f"{REMOTE_BASE}/{fn.replace('.jpg','.png')}",
    ]
    downloaded = False
    for rp in possible_paths:
        try:
            bn = f"{coords}_{direction}_{score:.0f}_{fn.replace('.jpg','.png')}"
            lp = os.path.join(nanshan_viz_dir, bn)
            if not os.path.exists(lp) or os.path.getsize(lp) == 0:
                sftp.get(rp, lp)
                sz = os.path.getsize(lp)
                if sz > 1000:
                    print(f"Sample [{score:.0f}分]: {bn} ({sz} bytes)")
                    downloaded = True
                    break
        except:
            pass
    if not downloaded:
        print(f"NOT FOUND: {coords}_{direction} {fn} score={score}")

sftp.close()
ssh.close()

print(f"\nSample viz saved to: {nanshan_viz_dir}")
print(f"Total sample files: {len(os.listdir(nanshan_viz_dir))}")
