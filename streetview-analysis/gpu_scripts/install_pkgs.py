#!/usr/bin/env python3
import paramiko, time, sys
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

# Step 1: 升级pip
print("="*60)
print("Step 1: 升级 pip")
print("="*60)
out = run(c, "pip3 install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120 2>&1 | tail -5", timeout=180)
print(out[-300:])

# Step 2: 安装核心依赖
print("\n" + "="*60)
print("Step 2: 安装 opencv-python-headless")
print("="*60)
out = run(c, "pip3 install opencv-python-headless -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 2>&1 | tail -5", timeout=360)
print(out[-300:])

# Step 3: 安装 transformers
print("\n" + "="*60)
print("Step 3: 安装 transformers")
print("="*60)
out = run(c, "pip3 install transformers -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 2>&1 | tail -5", timeout=360)
print(out[-300:])

# Step 4: 其他依赖
print("\n" + "="*60)
print("Step 4: 安装 pillow, scikit-image, matplotlib 等")
print("="*60)
out = run(c, "pip3 install pillow scikit-image matplotlib pandas numpy scipy -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 2>&1 | tail -5", timeout=360)
print(out[-300:])

# Step 5: 安装 albumentations
print("\n" + "="*60)
print("Step 5: 安装 albumentations")
print("="*60)
out = run(c, "pip3 install albumentations -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 2>&1 | tail -5", timeout=360)
print(out[-300:])

# 验证
print("\n" + "="*60)
print("验证安装")
print("="*60)
PYTHON = "/root/miniconda3/bin/python"
out = run(c, PYTHON + ' -c "import torch, cv2, PIL, numpy, scipy, sklearn, skimage, matplotlib, transformers; print(f\'torch={torch.__version__} cuda={torch.cuda.is_available()}\'); print(f\'cv2={cv2.__version__} transformers={transformers.__version__}\'); print(f\'skimage={skimage.__version__}\')"')
print(out)

c.close()
print("\n安装完成!")
