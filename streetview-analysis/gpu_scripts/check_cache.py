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
    ("torch hub cache", "ls -la /root/.cache/torch/hub/checkpoints/ 2>/dev/null"),
    ("pip list all", "pip3 list 2>/dev/null | grep -iE 'torch|cv2|transform|opencv|albument|skimage|scipy|pandas|sklearn|pillow'"),
    ("FCN coco weights", "ls -la /root/.cache/torch/hub/checkpoints/fcn* 2>/dev/null"),
    ("FCN cityscapes", "ls -la /root/.cache/torch/hub/checkpoints/*cityscapes* 2>/dev/null"),
    ("DeepLabV3", "ls -la /root/.cache/torch/hub/checkpoints/deeplabv3* 2>/dev/null"),
    ("hub cache all", "find /root/.cache/torch -type f 2>/dev/null"),
    ("cv2 check", PYTHON + ' -c "import cv2; print(cv2.getBuildInformation()[:300])"'),
    ("transformers check", PYTHON + ' -c "import transformers; print(transformers.__version__)"'),
]

for name, cmd in checks:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"\n# {name}:\n{out.strip()[:400]}")
    except Exception as e:
        print(f"# {name}: {e}")

# 测试直接从cityscapes本地数据
print("\nCityscapes数据集结构:")
out = run(c, "unzip -l /autodl-pub/data/cityscapes/gtFine_trainvaltest.zip 2>/dev/null | grep 'gtFine' | head -20")
print(out[:300])

# 检查S3DIS
print("\nS3DIS数据集:")
out = run(c, "ls -la /autodl-pub/data/S3DIS/ 2>/dev/null")
print(out[:300])

c.close()
