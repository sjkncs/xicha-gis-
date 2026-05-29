#!/usr/bin/env python3
"""Fix model upload and rewrite script to use direct torch.load."""
import paramiko, zipfile, os, time
from pathlib import Path

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"

LOCAL_ZIP = Path(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_segformer_b3.zip")
REMOTE_ZIP = "/root/autodl-tmp/models/segformer_b3.zip"
REMOTE_SNAP = "/root/autodl-tmp/models/snapshots/default"
REMOTE_SCRIPT = "/root/gis_project/seg_inference_v4.py"
INFERENCE_SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v4.py"

print("=" * 60)
print("Connecting...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()
ssh_exec = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# === Step 1: Remove old model dir and re-create ===
print("\n[1/5] Cleaning and creating model directory...")
ssh_exec(f"rm -rf /root/autodl-tmp/models/snapshots")
ssh_exec(f"mkdir -p {REMOTE_SNAP}")

# === Step 2: Upload zip ===
print(f"\n[2/5] Uploading model zip ({LOCAL_ZIP.stat().st_size/1024/1024:.1f}MB)...")
t0 = time.time()
def progress(c, t):
    if t > 0:
        print(f"\r  {c/1024/1024:.1f}/{t/1024/1024:.1f}MB ({c/t*100:.0f}%)", end="", flush=True)
sftp.put(str(LOCAL_ZIP), REMOTE_ZIP, callback=progress)
print(f"\nUploaded in {time.time()-t0:.1f}s")
sftp.close()

# === Step 3: Extract on server ===
print("\n[3/5] Extracting zip on server...")
out, err = ssh_exec(f"cd /root/autodl-tmp/models && unzip -o segformer_b3.zip && rm segformer_b3.zip && ls -lh snapshots/default/")
print(out[:400])
if err:
    print("STDERR:", err[:200])

# Verify
out, _ = ssh_exec(f"ls -lh {REMOTE_SNAP}/")
print("Extracted files:", out[:400])

# === Step 4: Write inference script with direct torch.load ===
print("\n[4/5] Writing inference script v4 (direct torch.load)...")

v4_script = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SegFormer B3 ADE20K 语义分割 - v4: 直接torch.load绕过HF repo_id验证"""
from __future__ import print_function
import os, sys, json, time, csv, math
from pathlib import Path

import torch
import numpy as np
from PIL import Image
import cv2

DEVICE = "cuda"

# 路径配置
MODEL_SNAP = Path("/root/autodl-tmp/models/snapshots/default")
DATA_DIR = Path("/root/autodl-tmp/streetview_analysis/images")
OUT_DIR = Path("/root/autodl-tmp/outputs/segmentation")
VIZ_DIR = OUT_DIR / "viz"
CHECKPOINT = OUT_DIR / "checkpoint.json"
LOG_FILE = Path("/root/gis_project/logs/seg_v4.log")

OUT_DIR.mkdir(parents=True, exist_ok=True)
VIZ_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# =====================================================================
# CITY_CLASSES - 修复版
# road: 6+11+52+13+91 (合并road+sidewalk+path+earth+dirt_track)
# green: 4+9+29 (tree+grass+field, 移除17plant)
# =====================================================================
CITY_CLASSES = {
    "building": [1, 25, 48],
    "road":     [6, 11, 52, 13, 91],
    "green":    [4, 9, 29],
    "sky":      [2],
    "vehicle":  [20, 80, 83, 102],
    "person":   [12],
    "water":    [21, 26, 60, 109, 128],
}

_color_entries = [
    (0,  115,115,115), (1,  180, 50, 50), (25, 170, 40, 40),
    (48, 160, 30, 30), (5,  175,170,160), (14, 130, 95, 65),
    (8,  100,100,100), (24, 145,115, 95), (15, 140,110, 90),
    (10, 130,110, 90), (23, 170,140,120), (33, 120,100, 80),
    (64, 150,120,100), (65, 130,110, 90), (36, 200,180, 60),
    (34, 200, 50, 50), (37, 180,170,155), (42, 160,155,130),
    (43, 175,145,100), (44, 170,140,100), (47, 140,130,115),
    (49, 160, 60, 30), (50, 170,175,170), (51, 120,100, 80),
    (55, 155,130,100), (56, 170,155,120), (57, 220,200,160),
    (58, 140,135,130), (59, 100, 95, 80), (61, 100, 95, 80),
    (84, 130,120,110), (85, 200,180, 60), (86, 180,160, 50),
    (87, 170,150, 40), (89, 150,135,110), (93, 110, 90, 80),
    (95, 155,135,110), (97, 160,135,105), (108,155,130,105),
    (135,180,155,110),(136,175,150,120),(137,175,160,  0),
    (138,175,160,130),(140,160,140,120),(142,165,150,125),
    (143,170,155,130),(144,175,145,115),(146,160,140,115),
    (147,165,145,120),
    (2,  135,206,250), (3,  150,125,100),
    (6,  230,140, 40), (11, 195,195,195),  # road=橙, sidewalk=浅灰
    (52, 210,160, 60), (13, 170,145,100),
    (91, 165,135, 80), (94, 145,125, 90),
    (46, 170,155,130), (62, 160,130,100),
    (4,    0,185, 40), (9,   30,200, 50),  # tree, grass
    (17,  50,160, 40), (29,  20,160, 30),  # plant(非指标), field
    (66,   0,220, 80), (16, 100,130, 90),
    (68,  95,120, 85), (72,   0,180, 40),
    (35, 120,110, 90), (113, 50,140,180), (104, 30,150,200),
    (21,   0,100,180), (26,   0,130,200), (60,   0,120,200),
    (109,  0, 80,160), (128,  0, 90,170),
    (7,  180,160,130), (19, 160,120, 80), (22, 180,160, 80),
    (27, 180,200,220), (28, 160,120, 80), (30, 170,140,100),
    (31, 155,130,100), (39, 115,105, 95), (40, 155,130,105),
    (41, 160,140,110), (45, 165,140,105), (67, 160,130, 80),
    (69, 130,115, 90), (75, 165,140,105), (81, 200,190,160),
    (82, 220,200,100), (98, 190,170, 40), (99, 165,140,100),
    (100,170,145, 95), (101,155,130,100), (105,180,160,130),
    (106,170,150,110), (110,180,160,130), (111,160,135,105),
    (112,165,140,110), (114,170,155,120), (115,175,150,115),
    (117,155,130,105), (118,165,145,110), (119,170,160,130),
    (120,180,140, 80), (121,155,135,110), (122,160,140,105),
    (123,170,150,110), (124,160,140,120), (125,165,145,115),
    (126,140, 90, 60), (129,160,135,110), (130,165,145,120),
    (131,170,155,125), (132,165,140,110), (133,175,150,120),
    (134,165,145,115), (139,130,120,110), (141,160,140,120),
    (145,160,140,115), (148,140,120,100), (149,170, 60, 40),
    (12,   0,  0,255), (20, 255,  0,  0),  # person=蓝, car=红
    (76, 100, 40, 20), (77, 160,140, 50), (79, 150, 80, 30),
    (80, 200,  0,  0), (83, 220,  0,  0),
    (90, 160,140,100), (102,190,  0,  0),
    (103,120, 60, 20), (116,130,110, 80), (127,170,130, 90),
]
COLOR_MAP = {cid: (r, g, b) for cid, r, g, b in _color_entries}


def log(msg, end="\\n", flush=True):
    ts = time.strftime("%H:%M:%S")
    line = "[{}] {}".format(ts, msg)
    print(line, end=end, flush=flush)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + (" " if end == " " else "\\n"))
    except Exception:
        pass


def load_checkpoint():
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"done": [], "results": []}


def save_checkpoint(data):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_model():
    """Load SegFormer B3 using direct torch.load to bypass HF repo_id requirement."""
    from transformers import SegformerConfig, SegformerImageProcessor
    log("Loading model from: {}".format(MODEL_SNAP))

    t0 = time.time()

    # Load processor from preprocessor_config.json
    processor = SegformerImageProcessor.from_pretrained(str(MODEL_SNAP))

    # Load config
    config = SegformerConfig.from_pretrained(str(MODEL_SNAP))
    from transformers import SegformerForSemanticSegmentation
    model = SegformerForSemanticSegmentation(config)

    # Load pretrained weights directly with torch
    model_path = MODEL_SNAP / "pytorch_model.bin"
    if model_path.exists():
        log("Loading weights from: {}".format(model_path))
        state_dict = torch.load(model_path, map_location="cpu")
        model.load_state_dict(state_dict, strict=False)
        del state_dict
        log("Weights loaded successfully!")
    else:
        log("ERROR: pytorch_model.bin not found at {}".format(model_path))
        raise FileNotFoundError(str(model_path))

    if torch.cuda.is_available():
        try:
            model = model.to("cuda")
            log("Model on CUDA")
        except Exception as e:
            log("CUDA failed: {}, using CPU".format(e))
    model.eval()

    gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"
    log("Model loaded in {:.1f}s | GPU: {}".format(time.time() - t0, gpu_name))
    return processor, model


def equirectangular_to_perspective(equirect, yaw, pitch, fov_h, fov_v, out_w, out_h):
    w_img, h_img = equirect.size
    output = np.zeros((out_h, out_w, 3), dtype=np.uint8)
    yr = math.radians(yaw)
    pr = math.radians(pitch)
    fhr = math.radians(fov_h)
    fvr = math.radians(fov_v)
    fx = (out_w / 2.0) / math.tan(fhr / 2.0)
    fy = (out_h / 2.0) / math.tan(fvr / 2.0)
    arr = np.array(equirect)
    cp = math.cos(pr)
    sp = math.sin(pr)
    cy = math.cos(yr)
    sy = math.sin(yr)
    for v in range(out_h):
        dv = (v - out_h / 2.0) / fy
        for u in range(out_w):
            du = (u - out_w / 2.0) / fx
            rx = du * cp * cy - dv * sp * sy
            ry = du * sp + dv * cp
            rz = -du * cp * sy + dv * sp * cy + 1.0
            rlen = math.sqrt(rx*rx + ry*ry + rz*rz)
            if rz == 0:
                continue
            theta = math.acos(rz / rlen)
            phi = math.atan2(ry, rx)
            px = int((phi / (2*math.pi) + 0.5) * w_img) % w_img
            py = int((theta / math.pi) * h_img)
            if 0 <= py < h_img:
                output[v, u] = arr[py, px]
    return Image.fromarray(output)


def process_single(img_path, processor, model):
    try:
        img = Image.open(img_path).convert("RGB")
        yaws = [-150, -90, -30, 30, 90, 150]
        weights = [0.08, 0.17, 0.25, 0.25, 0.17, 0.08]
        views = []
        for yaw in yaws:
            v = equirectangular_to_perspective(img, yaw, 0, 60, 50, 512, 512)
            views.append(v)
        seg_maps = []
        with torch.no_grad():
            for i in range(0, len(views), 4):
                batch = views[i:i+4]
                inputs = processor(images=batch, return_tensors="pt")
                inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
                outputs = model(**inputs)
                logits = outputs.logits
                logits = torch.nn.functional.interpolate(
                    logits, size=(512, 512), mode="bilinear", align_corners=False)
                preds = logits.argmax(dim=1).cpu().numpy()
                seg_maps.extend(preds)
        h, w = seg_maps[0].shape
        counts = np.zeros((h, w, 150), dtype=np.float32)
        for seg_map, wgt in zip(seg_maps, weights):
            for cid in range(150):
                counts[:, :, cid] += (seg_map == cid).astype(np.float32) * wgt
        combined = counts.argmax(axis=2).astype(np.uint8)
        metrics = compute_metrics(combined)
        metrics["pano_name"] = img_path.name
        metrics["num_views"] = len(views)
        return metrics, combined
    except Exception as e:
        log("  FAIL {}: {}".format(img_path.name, e))
        return None, None


def compute_metrics(pred):
    total = pred.size
    if total == 0:
        return {}
    m = {}
    for name, ids in CITY_CLASSES.items():
        count = np.isin(pred, ids).sum()
        m["pct_" + name] = round(float(count) / total * 100, 2)
    b = m.get("pct_building", 0)
    r = m.get("pct_road", 0)
    g = m.get("pct_green", 0)
    s = m.get("pct_sky", 0)
    m["openness"] = round((s + g + r) / max(b, 1) * 10, 2)
    m["building_density"] = round(b / 10, 2)
    m["walkability"] = round((g*0.3 + r*0.4 + s*0.2 + (100-b)*0.1) / 100 * 10, 2)
    return m


def save_vis(pred, name, viz_dir):
    try:
        h, w = pred.shape
        vis = np.zeros((h, w, 3), dtype=np.uint8)
        for cid, color in COLOR_MAP.items():
            mask = pred == cid
            if mask.any():
                vis[mask] = np.array(color, dtype=np.uint8)
        bg = (vis.sum(axis=2) == 0)
        vis[bg] = (80, 80, 80)
        out_path = viz_dir / (name + ".png")
        cv2.imwrite(str(out_path), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))
        orig_path = DATA_DIR / (name + ".jpg")
        if orig_path.exists():
            orig_bgr = cv2.imread(str(orig_path))
            if orig_bgr is not None:
                orig_rgb = cv2.cvtColor(orig_bgr, cv2.COLOR_BGR2RGB)
                if orig_rgb.shape[0] != h or orig_rgb.shape[1] != w:
                    orig_rgb = cv2.resize(orig_rgb, (w, h), interpolation=cv2.INTER_AREA)
                overlay = (orig_rgb.astype(np.float32) * 0.55
                          + vis.astype(np.float32) * 0.45).clip(0, 255).astype(np.uint8)
                overlay_path = viz_dir / (name + "__overlay.png")
                cv2.imwrite(str(overlay_path), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
    except Exception as e:
        log("  viz failed: {}".format(e))


def append_csv(metrics, csv_path):
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        keys = sorted(metrics.keys())
        writer = csv.DictWriter(f, fieldnames=keys)
        if write_header:
            writer.writeheader()
        writer.writerow(metrics)


def main():
    log("=" * 60)
    log("SegFormer B3 ADE20K - v4 修复版")
    log("road={} | green={}".format(CITY_CLASSES["road"], CITY_CLASSES["green"]))
    log("Data: {}".format(DATA_DIR))
    log("Output: {}".format(OUT_DIR))
    log("=" * 60)

    processor, model = load_model()

    all_jpg = sorted(list(DATA_DIR.glob("*.jpg")) + list(DATA_DIR.glob("*.JPG")))
    log("Found {} images".format(len(all_jpg)))

    if not all_jpg:
        log("ERROR: No images!")
        return

    ckpt = load_checkpoint()
    done_names = set(ckpt["done"])
    results = ckpt["results"]
    remaining = [f for f in all_jpg if f.name not in done_names]
    log("Remaining: {}/{}".format(len(remaining), len(all_jpg)))

    csv_path = OUT_DIR / "seg_results.csv"
    t_start = time.time()

    for i, img_path in enumerate(remaining):
        t_img = time.time()
        log("[{}/{}] {}...".format(i+1, len(remaining), img_path.name), end=" ", flush=True)
        metrics, pred = process_single(img_path, processor, model)
        if metrics:
            elapsed = time.time() - t_img
            metrics["process_time_s"] = round(elapsed, 2)
            results.append(metrics)
            done_names.add(img_path.name)
            append_csv(metrics, csv_path)
            save_vis(pred, img_path.stem, VIZ_DIR)
            save_checkpoint({"done": list(done_names), "results": results[-100:]})
            log("OK {:.1f}s | b:{:.1f}% r:{:.1f}% g:{:.1f}% s:{:.1f}% open:{:.1f}".format(
                elapsed, metrics.get("pct_building", 0), metrics.get("pct_road", 0),
                metrics.get("pct_green", 0), metrics.get("pct_sky", 0), metrics.get("openness", 0)))
        if (i + 1) % 10 == 0:
            elapsed_total = time.time() - t_start
            avg = elapsed_total / (i + 1)
            eta = avg * len(remaining)
            mem = torch.cuda.memory_allocated()/1024**3 if torch.cuda.is_available() else 0
            log("  Progress: {}/{} | Elapsed:{:.1f}min | ETA:{:.1f}min | Mem:{:.2f}GB".format(
                i+1, len(remaining), elapsed_total/60, eta/60, mem))

    total = time.time() - t_start
    log("===== DONE! {} images in {:.1f}min =====".format(len(results), total/60))


if __name__ == "__main__":
    main()
'''

# Write script locally
with open(INFERENCE_SCRIPT_LOCAL, "w", encoding="utf-8") as f:
    f.write(v4_script)
print("Script v4 written locally")

# Verify syntax
import ast
try:
    ast.parse(v4_script)
    print("Syntax OK")
except SyntaxError as e:
    print(f"Syntax error line {e.lineno}: {e.msg}")

# Upload script
print("\n[5/5] Uploading and starting inference...")
sftp = client.open_sftp()
sftp.put(INFERENCE_SCRIPT_LOCAL, REMOTE_SCRIPT)
sftp.close()
print("Script uploaded!")

# Clear old checkpoint
ssh_exec("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
print("Checkpoint cleared")

# Kill old processes
ssh_exec("pkill -f seg_inference 2>/dev/null; sleep 1; echo done")

# Start v4
start_cmd = "cd /root/gis_project && python3 -u seg_inference_v4.py > logs/seg_v4.log 2>&1 &"
client.exec_command(start_cmd, timeout=10)
print("Inference v4 started!")
time.sleep(8)

# Check log
stdin, stdout, stderr = client.exec_command("tail -30 /root/gis_project/logs/seg_v4.log", timeout=10)
log_out = stdout.read().decode().strip()
print("\n=== Log ===")
print(log_out)

# Check process
stdin, stdout, stderr = client.exec_command("ps aux | grep seg_inference | grep -v grep", timeout=5)
proc_out = stdout.read().decode().strip()
print("\nProcess:", proc_out or "NOT RUNNING")

# GPU
stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader", timeout=5)
gpu_out = stdout.read().decode().strip()
print("GPU mem:", gpu_out)

client.close()
print("\nDONE!")
