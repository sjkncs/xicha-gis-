#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
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
    ("all files root level", "find /root -maxdepth 3 -type f 2>/dev/null"),
    ("autodl-tmp deep", "find /autodl-tmp -maxdepth 5 -type f 2>/dev/null | head -30"),
    ("autodl-tmp dirs", "find /autodl-tmp -maxdepth 3 -type d 2>/dev/null | head -30"),
    ("/autodl-pub nuScenes", "ls -la /autodl-pub/data/nuScenes/ 2>/dev/null | head -10"),
    ("find any jpg", "find /root -name '*.jpg' 2>/dev/null | head -10; find /autodl-pub -name '*.jpg' 2>/dev/null | head -10"),
    ("find any csv", "find /root -name '*.csv' 2>/dev/null | head -20"),
    ("find any pth/pt", "find /root -name '*.pth' -o -name '*.pt' 2>/dev/null | head -10; find /autodl-pub -maxdepth 6 -name '*.pth' -o -name '*.pt' 2>/dev/null | head -10"),
    ("/root/autodl-tmp content", "ls -laR /autodl-tmp/ 2>/dev/null | head -50"),
    ("pip cache files", "find /root/.cache -type f 2>/dev/null | head -30"),
    ("gpu processes", "nvidia-smi; ps aux | grep python | grep -v grep | head -10"),
    ("net test HF", "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://huggingface.co 2>/dev/null"),
    ("net test PyTorch CDN", "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://download.pytorch.org 2>/dev/null"),
    ("net test TUNA", "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://pypi.tuna.tsinghua.edu.cn 2>/dev/null"),
    ("torch hub cache", "ls -la /root/.cache/torch/hub/checkpoints/ 2>/dev/null"),
    ("miniconda envs", "ls /root/miniconda3/envs/ 2>/dev/null"),
    ("/usr/bin python", "/usr/bin/python3 --version 2>/dev/null; /usr/bin/python3 -c 'import torch; print(torch.__version__)' 2>/dev/null"),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"\n# {name}:\n{out.strip()[:500]}\n")
    except Exception as e:
        print(f"# {name}: ERROR {e}")

c.close()
