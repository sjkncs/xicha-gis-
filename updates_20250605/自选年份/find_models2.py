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

checks = [
    ("GIS project", "ls -la /root/gis_project/ 2>/dev/null; ls -la /root/gis_project/models/ 2>/dev/null | head -20"),
    ("Other model dirs", "find /root -maxdepth 5 -type d -name 'models' -o -name 'weights' 2>/dev/null | head -10"),
    ("GIS project files", "find /root/gis_project -type f 2>/dev/null | head -30"),
    ("PyTorch download speed", "curl -s --connect-timeout 5 -o /dev/null -w '%{speed_download}' https://download.pytorch.org/models/resnet50-0676ba61.pth 2>/dev/null || echo 'failed'"),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"# {name}:\n{out.strip()[:500]}\n")
    except Exception as e:
        print(f"# {name}: ERROR {e}")

# 测试完整下载一个小的pytorch模型
print("\nTesting FCN model download...")
out = run(c, PYTHON + ' -c "'
    'from torchvision.models.segmentation.fcn import fcn_resnet50, FCN_ResNet50_Weights; '
    'm = fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT); print(\'FCN loaded, classes:\', m.classifier[4].out_channels)'
'"', timeout=600)
print("FCN:", out.strip()[:500])

c.close()
