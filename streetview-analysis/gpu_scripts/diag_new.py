#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"
PORT = 12996
USER = "root"
PASS = "roBbKv+ed3Vm"
PYTHON = "/root/miniconda3/bin/python"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()

checks = [
    ("nvidia-smi", "nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader"),
    ("GPU utilization", "nvidia-smi --query-gpu=utilization.gpu,utilization.memory --format=csv,noheader"),
    ("Python/PyTorch", PYTHON + ' -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else \'NO_GPU\')"'),
    ("Disk", "df -h / /autodl-pub/data 2>/dev/null | tail -3"),
    ("RAM", "free -h"),
    ("/root contents", "ls -la /root/"),
    ("/root dirs", "find /root -maxdepth 2 -type d | sort"),
    ("pip packages", PYTHON + ' -c "import transformers; print(transformers.__version__)" 2>&1'),
    ("pip other", PYTHON + ' -c "import cv2; import PIL; import numpy; import skimage; print(\'cv2,PIL,numpy,skimage OK\')" 2>&1'),
    ("ADE20K data", "ls /autodl-pub/data/ADEChallengeData2016/ 2>/dev/null"),
    ("images search", "find /root /autodl-pub -maxdepth 5 -type d -name '*baidu*' -o -type d -name '*street*' -o -type d -name '*nanshan*' -o -type d -name '*seg*' 2>/dev/null | head -20"),
    ("all files in root", "find /root -maxdepth 3 -type f 2>/dev/null | sort | head -30"),
    ("streetview_seg", "ls -la /root/streetview_seg/ 2>/dev/null; ls -la /root/streetview_seg/data/ 2>/dev/null; ls -la /root/streetview_seg/models/ 2>/dev/null; ls -la /root/streetview_seg/output/ 2>/dev/null"),
    ("autodl-tmp", "ls -la /autodl-tmp/ 2>/dev/null"),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"\n# {name}:\n{out.strip()[:400]}")
    except Exception as e:
        print(f"# {name}: ERROR {e}")

c.close()
