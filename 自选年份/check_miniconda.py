#!/usr/bin/env python3
"""使用已有miniconda环境 - 检查并安装transformers"""
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
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

print("=" * 60)
print("检查 miniconda PyTorch 环境")
print("=" * 60)
c = ssh()

cmds = [
    ('PyTorch+CUDA', PYTHON + ' -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else \'NO_GPU\')"'),
    ('transformers', PYTHON + ' -c "import transformers; print(transformers.__version__)"'),
    ('CUDA version', PYTHON + ' -c "import torch; print(torch.version.cuda)"'),
    ('pillow+numpy', PYTHON + ' -c "import PIL; import numpy; print(\'ok\')"'),
    ('ADE20K', 'ls /autodl-pub/data/ADEChallengeData2016/'),
    ('GPU memory', 'nvidia-smi --query-gpu=memory.used,memory.total --format=csv'),
]

for name, cmd in cmds:
    try:
        out = run(c, cmd)
        print(f"{name}: {out.strip()[:200]}")
    except Exception as e:
        print(f"{name}: ERROR - {e}")

c.close()
print("\nDone!")
