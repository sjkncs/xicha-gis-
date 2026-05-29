#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON = "/root/miniconda3/bin/python"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()

# 检查torchvision分割模型
print("1. torchvision segmentation models:")
out = run(c, PYTHON + ' -c "from torchvision.models.segmentation import fcn_resnet50, deeplabv3_resnet50, lrasnet_lowresnet34; print(\"FCN, DeepLabV3, LR-ASPP OK\")"')
print(out.strip())

# 测试直接从torch hub加载（不预下载）
print("\n2. FCN ResNet50 (Cityscapes 21类):")
start = time.time()
out = run(c, PYTHON + ' -c "'
    'import torch; from torchvision.models.segmentation.fcn import fcn_resnet50; '
    'try: m=fcn_resnet50(weights=\"DEFAULT\"); print(m.classifier[4].out_channels)'
    'except Exception as e: print(f\"Error: {e}\")'
'"', timeout=300)
elapsed = time.time() - start
print(f"Result: {out.strip()} ({elapsed:.1f}s)")

# 检查torch hub cache now
print("\n3. Torch hub cache after download:")
out = run(c, "ls -la /root/.cache/torch/hub/checkpoints/ 2>/dev/null")
print(out.strip())

# 测试DeepLabV3
print("\n4. DeepLabV3 ResNet50:")
start = time.time()
out = run(c, PYTHON + ' -c "'
    'import torch; from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50; '
    'try: m=deeplabv3_resnet50(weights=\"DEFAULT\"); print(m.classifier[4].out_channels)'
    'except Exception as e: print(f\"Error: {e}\")'
'"', timeout=300)
elapsed = time.time() - start
print(f"Result: {out.strip()} ({elapsed:.1f}s)")

# GPU速度测试 - 用无权重初始化
print("\n5. GPU推理速度 (无预训练权重):")
out = run(c, PYTHON + ' -c "'
    'import torch,time; from torchvision.models.segmentation.fcn import fcn_resnet50; '
    'm=fcn_resnet50(weights=None); '
    'import torch.nn as nn; '
    'm.classifier[4]=nn.Conv2d(512,21,bias=True); m=m.cuda(); m.eval(); '
    'x=torch.randn(1,3,512,512).cuda(); '
    'with torch.no_grad(): [m(x) for _ in range(10)]; '
    't0=time.time(); [m(x) for _ in range(50)]; torch.cuda.synchronize(); '
    "print(f\\'FCN random GPU: {50/(time.time()-t0):.1f} imgs/s\\')"
'"', timeout=60)
print(out.strip())

# LR-ASPP速度
print("\n6. LR-ASPP GPU速度:")
out = run(c, PYTHON + ' -c "'
    'import torch,time; from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34; '
    'm=lrasnet_lowresnet34(weights=None); m=m.cuda(); m.eval(); '
    'x=torch.randn(1,3,512,512).cuda(); '
    'with torch.no_grad(): [m(x) for _ in range(10)]; '
    't0=time.time(); [m(x) for _ in range(50)]; torch.cuda.synchronize(); '
    "print(f\\'LR-ASPP GPU: {50/(time.time()-t0):.1f} imgs/s\\')"
'"', timeout=60)
print(out.strip())

c.close()
