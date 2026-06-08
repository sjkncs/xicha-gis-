# -*- coding: utf-8 -*-
"""GPU服务器环境安装脚本 - 使用venv"""
import paramiko

HOST = 'connect.bjb1.seetacloud.com'
PORT = 10244
USER = 'root'
PASS = 'roBbKv+ed3Vm'

def do(client, cmd, timeout=120, verbose=True):
    if verbose: print(f"  CMD: {cmd[:80]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out and verbose:
        for l in out.split('\n')[:8]: print(f"    {l}")
    if err and 'warning' not in err.lower() and verbose:
        print(f"    ERR: {err[:200]}")
    return out

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
    print("=== Connected ===")

    # Step 1: System packages
    print("\n[1] apt update + install...")
    do(client, "apt-get update -qq 2>&1 | tail -3", timeout=120)
    do(client, "apt-get install -y -qq python3-venv python3-dev git wget curl 2>&1 | tail -3", timeout=120)

    # Step 2: Create venv
    print("\n[2] 创建venv...")
    do(client, "python3 -m venv /root/venv && /root/venv/bin/pip --version")
    do(client, "/root/venv/bin/pip install --upgrade pip 2>&1 | tail -2")

    # Step 3: Install PyTorch
    print("\n[3] 安装 PyTorch (CUDA 12.1)...")
    do(client,
       "/root/venv/bin/pip install torch torchvision torchaudio "
       "--index-url https://download.pytorch.org/whl/cu121 2>&1 | tail -5",
       timeout=600)

    # Verify PyTorch
    out = do(client,
        "python3 -c \"import torch; print('PyTorch:', torch.__version__, '| CUDA:', torch.cuda.is_available())\"")
    print(f"  {out.strip()}")

    # Step 4: Install libs
    print("\n[4] 安装分割库...")
    do(client,
       "/root/venv/bin/pip install timm transformers albumentations opencv-python-headless "
       "Pillow numpy pandas 2>&1 | tail -5",
       timeout=300)

    # Verify
    out = do(client, "python3 -c \"import timm, transformers; print('timm:', timm.__version__, '| transformers:', transformers.__version__)\"")
    print(f"  {out.strip()}")

    out = do(client, "python3 -c \"import cv2; print('OpenCV:', cv2.__version__)\"")
    print(f"  {out.strip()}")

    # Step 5: Working dirs
    print("\n[5] 创建目录...")
    do(client, "mkdir -p /root/streetview_seg/data /root/streetview_seg/output /root/streetview_seg/models")

    # Step 6: GPU check
    out = do(client, "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader")
    print(f"\n=== GPU: {out.strip()} ===")
    print("\n=== 环境安装完成 ===")
    client.close()

if __name__ == "__main__":
    main()
