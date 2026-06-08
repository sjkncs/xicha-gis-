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
    # GPU进程
    ("gpu full", "nvidia-smi"),
    ("ps python", "ps aux | grep python | grep -v grep | head -10"),
    # autodl-pub深度搜索
    ("autodl-pub all", "ls /autodl-pub/ 2>/dev/null | head -20"),
    ("autodl-pub sizes", "du -sh /autodl-pub/data/*/ 2>/dev/null | sort -h | tail -20"),
    ("autodl-pub find seg", "find /autodl-pub -maxdepth 4 -type d 2>/dev/null | grep -iE 'seg|street|baidu|nanshan|urban|access|障碍' | head -20"),
    # pip镜像测试
    ("TUNA pytorch test", "curl -s --connect-timeout 8 'https://pypi.tuna.tsinghua.edu.cn/simple/torch/' 2>/dev/null | head -5"),
    ("TUNA transformers test", "curl -s --connect-timeout 8 'https://pypi.tuna.tsinghua.edu.cn/simple/transformers/' 2>/dev/null | head -3"),
    # pip list
    ("pip list", "pip3 list 2>/dev/null | head -40"),
    # 系统python
    ("sys python torch", "/usr/bin/python3 -c 'import torch; print(torch.__version__)' 2>&1"),
    # torch hub cache
    ("torch hub", "ls -la /root/.cache/torch/hub/ 2>/dev/null"),
    ("torch checkpoints", "ls -la /root/.cache/torch/hub/checkpoints/ 2>/dev/null"),
    # 尝试pip install --dry-run
    ("pip install test cv2", "pip3 install opencv-python-headless -i https://pypi.tuna.tsinghua.edu.cn/simple --dry-run 2>&1 | head -5"),
    # autodl-pub data list
    ("autodl-pub data list", "ls /autodl-pub/data/ 2>/dev/null"),
    ("ADE20K zip check", "ls -la /autodl-pub/data/ADEChallengeData2016/ 2>/dev/null"),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"\n# {name}:\n{out.strip()[:600]}\n")
    except Exception as e:
        print(f"# {name}: ERROR {e}")

c.close()
