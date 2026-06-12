#!/usr/bin/env python3
"""
GPU服务器部署脚本 - 可达性障碍分析
"""
import paramiko, time, sys, io
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_WORK = "/root/autodl-tmp/streetview_seg"
LOCAL_IMG_DIR = Path(r"E:\xicha gis 智能定位\自选年份\baidu_streetview")
LOCAL_CSV = Path(r"E:\xicha gis 智能定位\自选年份\baidu_streetview\segmentation_results_v3\seg_final_clean.csv")
REMOTE_DATA = f"{REMOTE_WORK}/data"
REMOTE_SCRIPT = f"{REMOTE_WORK}/obstacle_gpu.py"
REMOTE_RESULTS = f"{REMOTE_WORK}/results"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=60):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def sftp_upload(local_path, remote_path, c):
    """上传单个文件或目录"""
    sftp = c.open_sftp()
    try:
        lp = Path(local_path)
        if lp.is_dir():
            # 创建远程目录
            sftp.stat(remote_path)  # 检查是否存在
        else:
            sftp.put(str(lp), remote_path)
            print(f"  Uploaded: {lp.name} -> {remote_path}")
    except FileNotFoundError:
        # 目录不存在则创建
        parts = remote_path.split('/')
        cur = ''
        for p in parts:
            cur += p + '/'
            try: sftp.stat(cur.rstrip('/'))
            except: sftp.mkdir(cur.rstrip('/'))
        if lp.is_file():
            sftp.put(str(lp), remote_path)
            print(f"  Uploaded: {lp.name}")
    sftp.close()

print("=" * 60)
print("Step 1: 环境准备")
print("=" * 60)
c = ssh()
out, err = run(c, "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
print("GPU:", out.strip())
out, err = run(c, "python3 -c 'import torch; print(torch.__version__)' 2>&1")
print("torch:", out.strip())
out, err = run(c, "pip3 list 2>/dev/null | grep -iE 'torch|transform' || echo 'not installed'")
print("packages:", out.strip()[:200])
out, err = run(c, f"mkdir -p {REMOTE_DATA} {REMOTE_RESULTS} && echo 'dirs ready'")
print(out)
c.close()

print("\n" + "=" * 60)
print("Step 2: 检查网络和安装依赖")
print("=" * 60)
c = ssh()
# 检查是否能访问PyTorch下载
out, err = run(c, "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://download.pytorch.org 2>/dev/null || echo 'unreachable'")
print("PyTorch CDN:", out.strip())
out, err = run(c, "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://mirrors.tuna.tsinghua.edu.cn 2>/dev/null || echo 'unreachable'")
print("TUNA mirror:", out.strip())
out, err = run(c, "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://pypi.tuna.tsinghua.edu.cn 2>/dev/null || echo 'unreachable'")
print("PyPI TUNA:", out.strip())
c.close()
