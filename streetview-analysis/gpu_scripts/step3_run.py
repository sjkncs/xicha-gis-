#!/usr/bin/env python3
"""分步执行：补传剩余图片 + 上传分析脚本 + 后台启动"""
import paramiko, time, json
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
OUT_DIR = REMOTE_DIR + "/output"
LOCAL_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

conn = ssh()
sftp = conn.open_sftp()

# === 1. 补传剩余图片 ===
print("=== 补传剩余图片 ===")
stdin, stdout, stderr = conn.exec_command(f"find {REMOTE_DIR}/images -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l", timeout=15)
remote_count = int(stdout.read().decode().strip())
print(f"服务器已有: {remote_count}张")

jpg_images = list(LOCAL_DIR.rglob("*.jpg"))
png_images = list(LOCAL_DIR.rglob("*.png"))
all_images = jpg_images + png_images
local_count = len(all_images)
print(f"本地共有: {local_count}张")

# 找出缺失的
uploaded = 0
for img in all_images:
    rel = str(img.relative_to(LOCAL_DIR)).replace("\\", "/")
    remote = f"{REMOTE_DIR}/images/{rel}"
    try:
        sftp.stat(remote)
    except:
        # 需要上传
        try:
            dirs = remote.rsplit("/", 1)[0]
            conn.exec_command(f"mkdir -p \"{dirs}\"", timeout=5)
            sftp.put(str(img), remote)
            uploaded += 1
        except:
            pass

print(f"补传: {uploaded}张")

# 确认最终数量
stdin, stdout, stderr = conn.exec_command(f"find {REMOTE_DIR}/images -name '*.jpg' -o -name '*.png' 2>/dev/null | wc -l", timeout=15)
total_remote = int(stdout.read().decode().strip())
print(f"服务器总计: {total_remote}张")

# === 2. 写分析脚本 ===
print("\n=== 上传分析脚本 ===")
script_content = r'''#!/usr/bin/python3
import os, sys, time, json, glob, cv2, numpy as np, torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.stdout.reconfigure(line_buffering=True)
print("START")

REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
OUT_DIR = REMOTE_DIR + "/output"
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(OUT_DIR + "/heatmaps", exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("DEVICE=" + str(device))

from torchvision.models.segmentation.fcn import fcn_resnet50, FCN_ResNet50_Weights
from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights

print("Loading FCN...")
fcn = fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT).to(device).eval()
print("Loading DeepLabV3...")
dlv3 = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT).to(device).eval()
print("MODELS_READY")

OBSTACLE_IDS = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17}

def segment(img_path, model):
    img = cv2.imread(img_path)
    if img is None:
        return None, None
    oh, ow = img.shape[:2]
    img_r = cv2.resize(img, (512, 512))
    rgb = cv2.cvtColor(img_r, cv2.COLOR_BGR2RGB)
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).float() / 255.0
    tensor = tensor.unsqueeze(0).to(device)
    with torch.no_grad():
        out = model(tensor)["out"].argmax(1).squeeze().cpu().numpy()
    out = cv2.resize(out.astype(np.uint8), (ow, oh), interpolation=cv2.INTER_NEAREST)
    return out, img

def calc_score(pred):
    h, w = pred.shape
    ids = list(OBSTACLE_IDS)
    bot_ob = np.sum(np.isin(pred[h//3:, :], ids))
    mid_ob = np.sum(np.isin(pred[h//3:2*h//3, :], ids))
    top_ob = np.sum(np.isin(pred[:h//3, :], ids))
    tot_pct = (bot_ob + mid_ob + top_ob) / (h * w) * 100
    bot_pct = bot_ob / (h//3 * w) * 100
    mid_pct = mid_ob / (h//3 * w) * 100
    top_pct = top_ob / (h//3 * w) * 100
    obs = tot_pct * 0.3 + bot_pct * 0.5 + mid_pct * 0.2
    return obs, tot_pct, bot_pct, mid_pct, top_pct

def make_heatmap(pred, img, out_path):
    h, w = pred.shape
    heat = np.zeros((h, w), dtype=np.float32)
    for c in OBSTACLE_IDS:
        mask = (pred == c).astype(np.float32)
        w2 = 1.5 if c in {9, 10} else (1.2 if c in {5, 6, 7} else (0.8 if c in {2, 3, 4} else 1.0))
        heat += mask * w2
    heat = np.clip(heat / (heat.max() + 1e-6) * 255, 0, 255).astype(np.uint8)
    color = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    blended = cv2.addWeighted(img, 0.6, color, 0.4, 0)
    cv2.imwrite(out_path, blended)

imgs = sorted(glob.glob(REMOTE_DIR + "/images/**/*.jpg", recursive=True) + glob.glob(REMOTE_DIR + "/images/**/*.png", recursive=True))
print("FOUND=" + str(len(imgs)))

if imgs:
    segment(imgs[0], fcn)

results = []
t0 = time.time()
for i, p in enumerate(imgs):
    rel = p.replace(REMOTE_DIR + "/images/", "").replace("\\", "/")
    parts = rel.replace(".jpg", "").replace(".png", "").split("/")
    district = parts[0] if len(parts) > 0 else "unk"
    street = parts[1] if len(parts) > 1 else "unk"
    community = parts[2] if len(parts) > 2 else "unk"
    fname = parts[-1] if len(parts) > 0 else "unk"

    pred, img = segment(p, fcn)
    if pred is None:
        continue
    obs, tot, bot, mid, top = calc_score(pred)

    sname = rel.replace("/", "_").replace("\\", "_").replace(".jpg", "").replace(".png", "")
    make_heatmap(pred, img, OUT_DIR + "/heatmaps/" + sname + "_fcn.jpg")

    r = {
        "file": rel, "filename": fname,
        "district": district, "street": street, "community": community,
        "obstacle_score": round(obs, 2), "obstacle_pct": round(tot, 2),
        "bottom_pct": round(bot, 2), "middle_pct": round(mid, 2), "top_pct": round(top, 2)
    }
    if i % 10 == 0:
        pred2, _ = segment(p, dlv3)
        if pred2 is not None:
            obs2, _, _, _, _ = calc_score(pred2)
            r["obstacle_score_dlv3"] = round(obs2, 2)

    results.append(r)
    if (i + 1) % 20 == 0:
        print("PROGRESS=" + str(i + 1) + "/" + str(len(imgs)))

elapsed = time.time() - t0
print("COMPLETE=" + str(len(results)) + " in " + str(round(elapsed, 1)) + "s (" + str(round(len(results) / max(elapsed, 0.1), 1)) + " img/s)")

with open(OUT_DIR + "/results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

street_stats = {}
for r in results:
    s = r.get("street", "unk")
    if s not in street_stats:
        street_stats[s] = []
    street_stats[s].append(r["obstacle_score"])

summary = {}
for s, scores in street_stats.items():
    summary[s] = {
        "count": len(scores),
        "mean_obstacle_score": round(sum(scores) / len(scores), 2),
        "max_obstacle_score": round(max(scores), 2),
        "min_obstacle_score": round(min(scores), 2)
    }

with open(OUT_DIR + "/street_summary.json", "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

all_scores = [r["obstacle_score"] for r in results]
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
streets = list(summary.keys())
axes[0].barh(streets, [summary[s]["mean_obstacle_score"] for s in streets], color="steelblue")
axes[0].set_xlabel("Obstacle Score (mean)")
axes[0].set_title("Obstacle Score by Street")
axes[0].grid(axis="x", alpha=0.3)
for i, s in enumerate(streets):
    axes[0].text(summary[s]["mean_obstacle_score"] + 0.1, i, str(summary[s]["mean_obstacle_score"]), va="center", fontsize=8)

axes[1].hist(all_scores, bins=20, color="coral", edgecolor="black", alpha=0.7)
axes[1].axvline(np.mean(all_scores), color="red", linestyle="--", label="Mean=" + str(round(np.mean(all_scores), 1)))
axes[1].set_xlabel("Obstacle Score")
axes[1].set_ylabel("Count")
axes[1].set_title("Obstacle Score Distribution")
axes[1].legend()
axes[1].grid(alpha=0.3)

plt.tight_layout()
plt.savefig(OUT_DIR + "/summary.png", dpi=150, bbox_inches="tight")
plt.close()
print("ANALYSIS_DONE")
'''

with sftp.open(REMOTE_DIR + "/analyze.py", "w") as f:
    f.write(script_content)
print("分析脚本已上传")

# === 3. 后台启动分析 ===
print("\n=== 启动后台分析 ===")
# 用nohup确保后台运行
run_cmd = f"cd {REMOTE_DIR} && nohup {PYTHON_SYS} analyze.py > {OUT_DIR}/analyze.log 2>&1 &"
conn.exec_command(run_cmd, timeout=10)
print(f"已启动: {run_cmd}")

time.sleep(5)

# 确认进程
stdin, stdout, stderr = conn.exec_command("pgrep -fa 'analyze.py' | head -3", timeout=10)
pid = stdout.read().decode().strip()
print(f"进程PID: {pid or '未找到'}")

# 等待分析完成
print("\n等待分析完成...")
for round_num in range(40):
    time.sleep(30)

    try:
        with sftp.open(OUT_DIR + "/results.json") as f:
            data = json.loads(f.read().decode("utf-8"))
        done = len(data)
    except:
        done = 0

    stdin2, stdout2, stderr2 = conn.exec_command("pgrep -f 'analyze.py' | wc -l", timeout=10)
    running = int(stdout2.read().decode().strip())

    print(f"  t+{(round_num+1)*30}s: {done}/{total_remote} (running={running})")

    if done >= total_remote and running == 0:
        print("分析完成!")
        break

# === 4. 下载结果 ===
print("\n下载结果...")
LOCAL_OUT = Path(r"e:\xicha gis 智能定位\自选年份")
for fname in ["results.json", "street_summary.json", "summary.png"]:
    try:
        sftp.get(OUT_DIR + "/" + fname, str(LOCAL_OUT / fname))
        print(f"  {fname} OK")
    except Exception as ex:
        print(f"  {fname} FAILED: {ex}")

# 下载热力图
print("\n下载热力图...")
try:
    heatmap_list = [f for f in sftp.listdir(OUT_DIR + "/heatmaps/") if f.endswith(".jpg")]
    heat_dir = LOCAL_OUT / "heatmaps"
    heat_dir.mkdir(exist_ok=True)
    for idx, hf in enumerate(heatmap_list[:30]):
        try:
            sftp.get(OUT_DIR + "/heatmaps/" + hf, str(heat_dir / hf))
        except:
            pass
    print(f"  {min(30, len(heatmap_list))} 张热力图")
except Exception as ex:
    print(f"  热力图失败: {ex}")

sftp.close()
conn.close()
print("\n=== 全部完成 ===")
