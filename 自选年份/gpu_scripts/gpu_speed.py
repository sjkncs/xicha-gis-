#!/usr/bin/env python3
import paramiko, time
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

PYTHON = "/root/miniconda3/bin/python"

tests = [
    ("1. Basic GPU test", PYTHON + ' -c "import torch; x=torch.randn(1000,1000).cuda(); print(torch.cuda.get_device_name(0)); print(x.sum().item())"'),
    ("2. FCN num classes", PYTHON + ' -c "from torchvision.models.segmentation.fcn import fcn_resnet50; m=fcn_resnet50(); print(m.classifier[4].out_channels)"'),
    ("3. DeepLabV3 num classes", PYTHON + ' -c "from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50; m=deeplabv3_resnet50(); print(m.classifier[4].out_channels)"'),
    ("4. cv2 check", PYTHON + ' -c "import cv2; print(cv2.__version__)"'),
    ("5. transformers check", PYTHON + ' -c "import transformers; print(transformers.__version__)"'),
    ("6. skimage check", PYTHON + ' -c "import skimage; print(skimage.__version__)"'),
]

for name, cmd in tests:
    try:
        out = run(c, cmd, timeout=60)
        print(f"  {name}: {out.strip()}")
    except Exception as e:
        print(f"  {name}: {e}")

# GPU速度测试 - 初始化模型 + 推理
print("\nGPU速度测试 (FCN):")
script = PYTHON + ' << PYSCRIPT\n'
script += 'import torch, time\n'
script += 'from torchvision.models.segmentation.fcn import fcn_resnet50\n'
script += 'import torch.nn as nn\n'
script += 'm = fcn_resnet50()\n'
script += 'm.classifier[4] = nn.Conv2d(512, 21, bias=True)\n'
script += 'm = m.cuda()\n'
script += 'm.eval()\n'
script += 'x = torch.randn(1, 3, 512, 512).cuda()\n'
script += 'with torch.no_grad():\n'
script += '    for _ in range(5): m(x)\n'
script += '    torch.cuda.synchronize()\n'
script += 't0 = time.time()\n'
script += 'with torch.no_grad():\n'
script += '    for _ in range(50): m(x)\n'
script += 'torch.cuda.synchronize()\n'
script += 'fps = 50 / (time.time() - t0)\n'
script += 'print("FCN GPU FPS:", fps)\n'
script += 'PYSCRIPT'

out = run(c, script, timeout=120)
print(out.strip())

# DeepLabV3速度测试
print("\nGPU速度测试 (DeepLabV3):")
script2 = PYTHON + ' << PYSCRIPT\n'
script2 += 'import torch, time\n'
script2 += 'from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50\n'
script2 += 'import torch.nn as nn\n'
script2 += 'm = deeplabv3_resnet50()\n'
script2 += 'm.classifier[4] = nn.Conv2d(256, 21, bias=True)\n'
script2 += 'm = m.cuda()\n'
script2 += 'm.eval()\n'
script2 += 'x = torch.randn(1, 3, 512, 512).cuda()\n'
script2 += 'with torch.no_grad():\n'
script2 += '    for _ in range(5): m(x)\n'
script2 += '    torch.cuda.synchronize()\n'
script2 += 't0 = time.time()\n'
script2 += 'with torch.no_grad():\n'
script2 += '    for _ in range(50): m(x)\n'
script2 += 'torch.cuda.synchronize()\n'
script2 += 'fps = 50 / (time.time() - t0)\n'
script2 += 'print("DeepLabV3 GPU FPS:", fps)\n'
script2 += 'PYSCRIPT'

out = run(c, script2, timeout=120)
print(out.strip())

c.close()
