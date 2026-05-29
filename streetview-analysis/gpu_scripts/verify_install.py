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

pkgs = [
    ("torch", PYTHON + ' -c "import torch; print(torch.__version__, torch.cuda.is_available())"'),
    ("cv2", PYTHON + ' -c "import cv2; print(cv2.__version__)"'),
    ("PIL", PYTHON + ' -c "from PIL import Image; print(Image.__version__)"'),
    ("numpy", PYTHON + ' -c "import numpy; print(numpy.__version__)"'),
    ("scipy", PYTHON + ' -c "import scipy; print(scipy.__version__)"'),
    ("skimage", PYTHON + ' -c "import skimage; print(skimage.__version__)"'),
    ("matplotlib", PYTHON + ' -c "import matplotlib; print(matplotlib.__version__)"'),
    ("pandas", PYTHON + ' -c "import pandas; print(pandas.__version__)"'),
    ("transformers", PYTHON + ' -c "import transformers; print(transformers.__version__)"'),
    ("sklearn", PYTHON + ' -c "import sklearn; print(sklearn.__version__)"'),
    ("albumentations", PYTHON + ' -c "import albumentations; print(albumentations.__version__)"'),
]

print("包安装验证:")
for name, cmd in pkgs:
    try:
        out = run(c, cmd)
        print(f"  {name}: {out.strip()}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

# GPU测试
print("\nGPU测试:")
out = run(c, PYTHON + ' -c "import torch; x=torch.randn(1000,1000).cuda(); print(torch.cuda.get_device_name(0)); print(x.sum().item())"')
print("GPU:", out.strip())

# torchvision segmentation模型
print("\n测试 torchvision segmentation:")
out = run(c, PYTHON + ' -c "from torchvision.models.segmentation.fcn import fcn_resnet50, FCN_ResNet50_Weights; m=fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT); print(\"FCN classes:\", m.classifier[4].out_channels)"', timeout=300)
print("FCN:", out.strip()[:200])

# 检查Cityscapes数据集
print("\nCityscapes数据集:")
out = run(c, "ls -la /autodl-pub/data/cityscapes/ 2>/dev/null | head -5")
print(out.strip())

# torchvision GPU速度测试
print("\nFCN GPU速度测试:")
out = run(c, PYTHON + ' -c "'
    'import torch,time; from torchvision.models.segmentation.fcn import fcn_resnet50,FCN_ResNet50_Weights; '
    'm=fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT).cuda(); m.eval(); '
    'x=torch.randn(1,3,512,512).cuda(); '
    'with torch.no_grad(): [m(x) for _ in range(5)]; '
    't0=time.time(); [m(x) for _ in range(20)]; torch.cuda.synchronize(); '
    "print(f\\'FCN GPU: {20/(time.time()-t0):.1f} imgs/s\\')"
'"', timeout=300)
print(out.strip())

c.close()
