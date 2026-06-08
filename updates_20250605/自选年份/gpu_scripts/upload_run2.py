#!/usr/bin/env python3
"""上传街景图片到GPU + 运行障碍分割分析"""
import paramiko, time, json
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 12996
USER = "root"
PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
LOCAL_DIR = Path(r"e:\xicha gis 智能定位\自选年份\baidu_streetview")

jpg_images = list(LOCAL_DIR.rglob("*.jpg"))
png_images = list(LOCAL_DIR.rglob("*.png"))
all_images = jpg_images + png_images
print(f"找到 {len(all_images)} 张图片")

def do_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

conn = do_ssh()
sftp_conn = conn.open_sftp()

# 1. 创建远程目录
print("创建目录...")
for d in [REMOTE_DIR, REMOTE_DIR + "/images", REMOTE_DIR + "/output"]:
    try:
        sftp_conn.mkdir(d)
    except:
        pass
print("目录就绪")

# 2. 上传图片
print(f"上传 {len(all_images)} 张图片...")
uploaded = 0
errors = 0
for img in all_images:
    rel = str(img.relative_to(LOCAL_DIR)).replace("\\", "/")
    remote = f"{REMOTE_DIR}/images/{rel}"
    dirs = remote.rsplit("/", 1)[0]
    # 用SSH mkdir -p 创建嵌套目录
    conn.exec_command(f"mkdir -p \"{dirs}\"", timeout=10)
    try:
        sftp_conn.put(str(img), remote)
        uploaded += 1
        if uploaded % 50 == 0:
            print(f"  {uploaded}/{len(all_images)}")
    except Exception as ex:
        errors += 1
        if errors <= 3:
            print(f"  错误 {img.name}: {ex}")
print(f"上传完成: {uploaded}张成功, {errors}失败")

# 3. 写分析脚本到服务器
analysis_script = '''#!/usr/bin/python3
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
    bot_ob = np.sum(np.isin(pred[h//3:, :], list(OBSTACLE_IDS)))
    mid_ob = np.sum(np.isin(pred[h//3:2*h//3, :], list(OBSTACLE_IDS)))
    top_ob = np.sum(np.isin(pred[:h//3, :], list(OBSTACLE_IDS)))
    tot_pct = (bot_ob + mid_ob + top_ob) / (h * w) * 100
    bot_pct = bot_ob / (h//3 * w) * 100
    mid_pct = mid_ob / (h//3 * w) * 100
    top_pct = top_ob / (h//3 * w) * 100
    obs = tot_pct * 0.3 + bot_pct * 0.5 + mid_pct * 0.2
    return round(obs, 2), round(tot_pct, 2), round(bot_pct, 2), round(mid_pct, 2), round(top_pct, 2)

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
print("FOUND_IMAGES=" + str(len(imgs)))

if imgs:
    segment(imgs[0], fcn)

results = []
t0 = time.time()
for i, p in enumerate(imgs):
    rel = p.replace(REMOTE_DIR + "/images/", "").replace("\\\\", "/")
    parts = rel.replace(".jpg", "").replace(".png", "").split("/")
    district = parts[0] if len(parts) > 0 else "unk"
    street = parts[1] if len(parts) > 1 else "unk"
    community = parts[2] if len(parts) > 2 else "unk"
    fname = parts[-1] if len(parts) > 0 else "unk"

    pred, img = segment(p, fcn)
    if pred is None:
        continue
    obs, tot, bot, mid, top = calc_score(pred)

    sname = rel.replace("/", "_").replace("\\\\", "_").replace(".jpg", "").replace(".png", "")
    heat_path = OUT_DIR + "/heatmaps/" + sname + "_fcn.jpg"
    make_heatmap(pred, img, heat_path)

    r = {
        "file": rel, "filename": fname,
        "district": district, "street": street, "community": community,
        "obstacle_score": obs, "obstacle_pct": tot,
        "bottom_pct": bot, "middle_pct": mid, "top_pct": top
    }
    if i % 10 == 0:
        pred2, _ = segment(p, dlv3)
        if pred2 is not None:
            obs2, _, _, _, _ = calc_score(pred2)
            r["obstacle_score_dlv3"] = obs2

    results.append(r)
    if (i + 1) % 50 == 0:
        print("PROGRESS=" + str(i + 1) + "/" + str(len(imgs)))

elapsed = time.time() - t0
print("COMPLETE=" + str(len(results)) + " images in " + str(round(elapsed, 1)) + "s (" + str(round(len(results) / max(elapsed, 0.1), 1) + " img/s)")

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

with sftp_conn.open(REMOTE_DIR + "/analyze.py", "w") as f:
    f.write(analysis_script)
print("分析脚本已写入")

# 4. 运行分析
print("\n启动GPU分析...")
channel = conn.get_transport().open_session()
channel.exec_command(PYTHON_SYS + " " + REMOTE_DIR + "/analyze.py 2>&1")

time.sleep(20)

# 监控进度
total_imgs = len(all_images)
for round_num in range(40):
    time.sleep(30)

    try:
        with sftp_conn.open(OUT_DIR + "/results.json") as f:
            data = json.loads(f.read().decode("utf-8"))
        done = len(data)
    except:
        done = 0

    stdin2, stdout2, stderr2 = conn.exec_command("pgrep -f 'analyze.py' | head -1", timeout=10)
    pid = stdout2.read().decode().strip()

    print(f"  t+{(round_num+1)*30}s: {done}/{total_imgs} ({pid or 'FINISHED'})")

    if done >= total_imgs and not pid:
        print("分析完成!")
        break
    if round_num > 38:
        print("超时")
        break

# 5. 下载结果
print("\n下载结果...")
LOCAL_OUT = Path(r"e:\xicha gis 智能定位\自选年份")
for fname in ["results.json", "street_summary.json", "summary.png"]:
    try:
        sftp_conn.get(OUT_DIR + "/" + fname, str(LOCAL_OUT / fname))
        print(f"  {fname} OK")
    except Exception as ex:
        print(f"  {fname} FAILED: {ex}")

# 6. 下载热力图
print("\n下载热力图样本...")
try:
    heatmap_list = [f for f in sftp_conn.listdir(OUT_DIR + "/heatmaps/") if f.endswith(".jpg")]
    heat_dir = LOCAL_OUT / "heatmaps"
    heat_dir.mkdir(exist_ok=True)
    for idx, hf in enumerate(heatmap_list[:30]):
        try:
            sftp_conn.get(OUT_DIR + "/heatmaps/" + hf, str(heat_dir / hf))
        except:
            pass
    print(f"  {min(30, len(heatmap_list))} 张热力图完成")
except Exception as ex:
    print(f"  热力图下载失败: {ex}")

sftp_conn.close()
conn.close()
print("\n=== 全部完成 ===")
