# -*- coding: utf-8 -*-
"""
GPU服务器环境安装 + 语义分割推理 自动化脚本
Run locally via paramiko
"""
import paramiko
import time
import sys

HOST = 'connect.bjb1.seetacloud.com'
PORT = 10244
USER = 'root'
PASS = 'roBbKv+ed3Vm'

def ssh_cmd(client, cmd, timeout=120):
    """Execute command and return stdout"""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if err and 'Warning' not in err and 'apt-list' not in err:
        print(f"  STDERR: {err[:200]}")
    return out

def ssh_exec(client, cmd, timeout=300):
    """Execute command, print output, return"""
    print(f"  CMD: {cmd[:80]}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=False)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out:
        for line in out.split('\n')[:5]:
            print(f"    {line}")
    if err and 'warning' not in err.lower() and 'warning:' not in err.lower():
        print(f"    ERR: {err[:200]}")
    return out

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
    print("=== Connected ===")

    # ============================================================
    # Step 1: Install Python + pip
    # ============================================================
    print("\n[1] 安装 Python & pip...")
    ssh_exec(client, "apt-get update -qq")
    ssh_exec(client, "apt-get install -y -qq python3 python3-pip python3-venv python3-dev git wget curl")

    # Verify python
    out = ssh_cmd(client, "which python3 && python3 --version")
    print(f"  Python: {out.strip()}")

    # ============================================================
    # Step 2: Install PyTorch with CUDA
    # ============================================================
    print("\n[2] 安装 PyTorch + torchvision (CUDA 12.x)...")
    torch_install = (
        "pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121 "
        "--quiet --break-system-packages 2>&1 | tail -5"
    )
    ssh_exec(client, torch_install, timeout=600)

    out = ssh_cmd(client, "python3 -c \"import torch; print(f'PyTorch:{torch.__version__} CUDA:{torch.cuda.is_available()} VRAM:{torch.cuda.get_device_properties(0).total_mem/1e9:.1f}GB')\"")
    print(f"  {out.strip()}")

    # ============================================================
    # Step 3: Install segmentation libraries
    # ============================================================
    print("\n[3] 安装分割相关库...")
    libs = (
        "pip3 install --quiet --break-system-packages "
        "timm transformers albumentations opencv-python-headless Pillow "
        "numpy pandas matplotlib scipy scikit-image 2>&1 | tail -5"
    )
    ssh_exec(client, libs, timeout=300)

    out = ssh_cmd(client, "python3 -c \"import timm, transformers; print('timm:', timm.__version__, 'transformers:', transformers.__version__)\"")
    print(f"  {out.strip()}")

    # ============================================================
    # Step 4: Create working directory
    # ============================================================
    print("\n[4] 创建工作目录...")
    ssh_exec(client, "mkdir -p /root/streetview_seg/data /root/streetview_seg/output /root/streetview_seg/models")
    out = ssh_cmd(client, "ls -la /root/streetview_seg/")
    print(f"  {out.strip()}")

    print("\n=== 环境安装完成 ===")
    client.close()

if __name__ == "__main__":
    main()
