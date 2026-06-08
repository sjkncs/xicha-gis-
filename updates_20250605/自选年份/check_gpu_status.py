# -*- coding: utf-8 -*-
"""检查GPU服务器当前状态"""
import paramiko

HOST = 'connect.bjb1.seetacloud.com'
PORT = 10244
USER = 'root'
PASS = 'roBbKv+ed3Vm'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
print("Connected")

cmds = [
    ("Python", "python3 --version"),
    ("venv存在?", "ls /root/venv/bin/python3 2>/dev/null && /root/venv/bin/python3 --version"),
    ("torch已装?", "/root/venv/bin/python3 -c \"import torch; print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available())\" 2>/dev/null || echo 'NO_TORCH'"),
    ("timm已装?", "/root/venv/bin/python3 -c \"import timm; print('timm:', timm.__version__)\" 2>/dev/null || echo 'NO_TIMM'"),
    ("工作目录", "ls -la /root/streetview_seg/"),
    ("GPU", "nvidia-smi --query-gpu=name,memory.free --format=csv,noheader"),
    ("pip version", "/root/venv/bin/pip --version"),
]

for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    print(f"\n[{name}]")
    print(f"  OUT: {out}")
    if err and err != out:
        print(f"  ERR: {err[:200]}")

client.close()
