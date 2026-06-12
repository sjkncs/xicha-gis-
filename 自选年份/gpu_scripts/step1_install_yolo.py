#!/usr/bin/env python3
"""检查服务器 + 安装 YOLO 所需依赖"""
import paramiko, os, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()

def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, err, exit_code

# ========== 阶段1: 安装 ultralytics ==========
print("=== 1. 安装 ultralytics ===")
out, err, ec = run(c, "pip install -q ultralytics 2>&1 | tail -5")
print(f"[{ec}] {out}")
if err and "error" in err.lower(): print(f"ERR: {err[-300:]}")

# ========== 阶段2: 下载模型权重 ==========
print("\n=== 2. 下载 YOLO 模型权重 ===")
models = {
    "yolo11x": "yolo11x.pt",
    "yolo11l": "yolo11l.pt",
    "yolov8x-oiv7": "yolov8x-oiv7.pt",
}

model_dir = f"{REMOTE_DIR}/yolo_models"
run(c, f"mkdir -p {model_dir}")

for name, fname in models.items():
    out_path = f"{model_dir}/{fname}"
    # 检查是否已存在
    try:
        sftp.stat(out_path)
        size = sftp.stat(out_path).st_size
        print(f"  {name}: 已存在 ({size//1024//1024}MB) 跳过")
        continue
    except:
        pass

    # 下载
    if name == "yolo11x":
        url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x.pt"
    elif name == "yolo11l":
        url = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11l.pt"
    else:  # oiv7
        url = "https://github.com/ultralytics/ultralytics/releases/download/v8.3.0/yolov8x-oiv7.pt"

    print(f"  下载 {name} ({url.split('/')[-1]})...")
    out, err, ec = run(c,
        f"cd {model_dir} && wget -q --show-progress -O {fname} '{url}' 2>&1 | tail -3",
        timeout=600)
    if ec == 0:
        out2, _, _ = run(c, f"ls -lh {model_dir}/{fname}")
        print(f"  OK: {out2}")
    else:
        print(f"  FAILED [{ec}]: {err[-200:]}")

# ========== 阶段3: 验证导入 ==========
print("\n=== 3. 验证 ultralytics ===")
out, err, ec = run(c, "python3 -c 'from ultralytics import YOLO; print(\"ultralytics OK, version:\", __import__(\"ultralytics\").__version__)'")
print(f"[{ec}] {out}")
if err: print(f"err: {err[:200]}")

# ========== 阶段4: 列出所有可用模型文件 ==========
print("\n=== 4. 可用模型 ===")
out, err, ec = run(c, f"find {model_dir} -name '*.pt' -o -name '*.pth' 2>/dev/null | xargs ls -lh 2>/dev/null || echo 'no models yet'")
print(out)

# ========== 阶段5: GPU确认 ==========
print("\n=== 5. GPU 状态 ===")
out, err, ec = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")
print(out)

sftp.close()
c.close()
print("\n=== 完成 ===")
