#!/usr/bin/env python3
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

c = ssh()

# 确认FCN权重已缓存
print("确认FCN_ResNet50权重已缓存...")
out = run(c, f"ls -la ~/.cache/torch/hub/checkpoints/ 2>/dev/null")
print(out.strip())

# 测试DeepLabV3加载速度
print("\n测试DeepLabV3加载...")
start = time.time()
out = run(c, PYTHON + ' -c "'
    'from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights; '
    'm = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT); '
    'print(\"DeepLabV3 classes:\", m.classifier[4].out_channels)'
'"', timeout=300)
elapsed = time.time() - start
print(f"DeepLabV3: {out.strip()} ({elapsed:.1f}s)")

# 检查torchvision segmentation可用模型
print("\n可用 segmentation 模型:")
out = run(c, PYTHON + ' -c "'
    'from torchvision.models.segmentation import fcn_resnet50, deeplabv3_resnet50, lrasnet_lowresnet34; '
    'print(\"FCN, DeepLabV3, LR-ASPP OK\")'
'"')
print(out.strip())

# 检查GPU速度
print("\nGPU推理速度测试...")
out = run(c, PYTHON + ' -c "'
    'import torch; from torchvision.models.segmentation.fcn import fcn_resnet50, FCN_ResNet50_Weights; '
    'm = fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT).cuda(); '
    'import time; x = torch.randn(1,3,512,512).cuda(); '
    'for _ in range(5): m(x); torch.cuda.synchronize(); '
    't0=time.time(); '
    'for _ in range(10): m(x); torch.cuda.synchronize(); '
    'print(f\\"FCN GPU: {10/(time.time()-t0):.1f} imgs/s\\")'
'"', timeout=120)
print(out.strip())

# 检查CUDA版本匹配
out = run(c, PYTHON + ' -c "'
    'import torch; print(f\\"torch={torch.__version__} cuda={torch.version.cuda} cudnn={torch.backends.cudnn.version()}\\")'
'"')
print("CUDA:", out.strip())

c.close()
