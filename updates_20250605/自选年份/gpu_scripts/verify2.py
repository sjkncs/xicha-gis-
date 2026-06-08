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

# 检查cv2和transformers具体问题
tests = [
    ("cv2 version", PYTHON + ' -c "import cv2; print(cv2.__version__)"'),
    ("cv2 build info", PYTHON + ' -c "import cv2; print(cv2.getBuildInformation()[:500])"'),
    ("transformers version", PYTHON + ' -c "import transformers; print(transformers.__version__)"'),
    ("transformers quick", PYTHON + ' -c "import transformers; print(\"OK\")"'),
    ("scipy", PYTHON + ' -c "import scipy; print(scipy.__version__)"'),
    ("skimage", PYTHON + ' -c "import skimage; print(skimage.__version__)"'),
    ("pandas", PYTHON + ' -c "import pandas; print(pandas.__version__)"'),
    ("sklearn", PYTHON + ' -c "import sklearn; print(sklearn.__version__)"'),
    ("albumentations", PYTHON + ' -c "import albumentations; print(albumentations.__version__)"'),
    ("pip list full", "pip3 list 2>/dev/null"),
]

for name, cmd in tests:
    try:
        out = run(c, cmd)
        if out.strip():
            print(f"{name}: {out.strip()[:200]}")
    except Exception as e:
        print(f"{name}: EXCEPTION {e}")

# 测试FCN加载 + GPU速度（先下载权重）
print("\n测试FCN加载...")
out = run(c, PYTHON + ' -c "'
    'import torch,time; '
    'from torchvision.models.segmentation.fcn import fcn_resnet50,FCN_ResNet50_Weights; '
    'm=fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT).cuda(); m.eval(); '
    'print(\"FCN loaded!\"); '
    'x=torch.randn(1,3,512,512).cuda(); '
    'with torch.no_grad(): [m(x) for _ in range(5)]; '
    't0=time.time(); [m(x) for _ in range(20)]; torch.cuda.synchronize(); '
    "print(f\\'FCN GPU: {20/(time.time()-t0):.1f} imgs/s\\')"
'"', timeout=600)
print(out.strip())

# 测试DeepLabV3
print("\n测试DeepLabV3...")
out = run(c, PYTHON + ' -c "'
    'import torch,time; '
    'from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50,DeepLabV3_ResNet50_Weights; '
    'm=deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT).cuda(); m.eval(); '
    'print(\"DeepLabV3 loaded!\"); '
    'x=torch.randn(1,3,512,512).cuda(); '
    'with torch.no_grad(): [m(x) for _ in range(5)]; '
    't0=time.time(); [m(x) for _ in range(20)]; torch.cuda.synchronize(); '
    "print(f\\'DeepLabV3 GPU: {20/(time.time()-t0):.1f} imgs/s\\')"
'"', timeout=600)
print(out.strip())

c.close()
