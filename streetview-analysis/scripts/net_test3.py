#!/usr/bin/env python3
import paramiko
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

c = ssh()
tests = [
    ("GitHub releases", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://github.com 2>/dev/null"),
    ("GitHub raw", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://raw.githubusercontent.com 2>/dev/null"),
    ("GitHub api", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://api.github.com 2>/dev/null"),
    ("PyTorch hub", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://download.pytorch.org 2>/dev/null"),
    ("PyTorch hub assets", "curl -s --connect-timeout 8 'https://download.pytorch.org/whl/torch_stable.html' 2>/dev/null | head -3"),
    ("Torchvision models", "curl -s --connect-timeout 8 'https://pytorch.org/docs/stable/torchvision/models.html' 2>/dev/null | grep -i 'segmentation' | head -3"),
]

for name, cmd in tests:
    try:
        out = run(c, cmd)
        print(f"  {name}: {out.strip()[:200]}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

# 检查ADE20K数据内容
print("\nChecking ADE20K data...")
out = run(c, f"cd /tmp && unzip -l /autodl-pub/data/ADEChallengeData2016/ADEChallengeData2016.zip 2>/dev/null | head -30")
print(out[:500])

# 检查PyTorch segmentation模型
print("\nPyTorch segmentation models available:")
out = run(c, PYTHON + ' -c "from torchvision.models.segmentation import fcn_resnet50, deeplabv3_resnet50; print(\'FCN, DeepLabV3 OK\')"')
print(out.strip())

c.close()
