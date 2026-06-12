#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

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
    ("PyTorch version", "/root/miniconda3/bin/python -c 'import torch; print(torch.__version__+chr(32)+\"cuda=\"+str(torch.cuda.is_available()))'"),
    ("CUDA version", "/root/miniconda3/bin/python -c 'import torch; print(\"CUDA:\",torch.version.cuda)'"),
    ("cuDNN", "/root/miniconda3/bin/python -c 'import torch; print(\"cuDNN:\",torch.backends.cudnn.version())'"),
    ("GPU test", "/root/miniconda3/bin/python -c 'import torch; x=torch.randn(100,100).cuda(); print(torch.cuda.get_device_name(0))'"),
    ("Install log", "tail -20 /root/autodl-tmp/pytorch_install.log 2>/dev/null || echo 'no log'"),
    ("pip list torch", "pip3 list 2>/dev/null | grep -iE 'torch|vision'"),
    ("GPU memory", "nvidia-smi --query-gpu=memory.used,memory.total --format=csv"),
    ("GPU processes", "ps aux | grep python | grep -v grep | head -5"),
    ("Torch hub", "ls /root/.cache/torch/hub/checkpoints/ 2>/dev/null"),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"  {name}: {out.strip()[:200]}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

c.close()
