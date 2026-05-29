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

print("=" * 60)
print("测试 torchvision 预训练模型 (ADE20K)")
print("=" * 60)

# 测试FCN_ResNet50_Weights 和 DeepLabV3_ResNet50_Weights
out = run(c, PYTHON + ' -c "'
    'from torchvision.models.segmentation.fcn import FCN_ResNet50_Weights, fcn_resnet50; '
    'from torchvision.models.segmentation.deeplabv3 import DeepLabV3_ResNet50_Weights, deeplabv3_resnet50; '
    'print(\"ADE20K num_classes:\", 150); '
    'w1 = FCN_ResNet50_Weights.DEFAULT.get_home_download_ratio; print(\"FCN weights:\", FCN_ResNet50_Weights.DEFAULT); '
    'w2 = DeepLabV3_ResNet50_Weights.DEFAULT.get_home_download_ratio; print(\"DeepLabV3 weights:\", DeepLabV3_ResNet50_Weights.DEFAULT)'
'"')
print(out.strip())

# 测试能否加载权重（不下载）
print("\n尝试加载FCN (不下载weights)...")
out = run(c, PYTHON + ' -c "'
    'from torchvision.models.segmentation.fcn import fcn_resnet50, FCN_ResNet50_Weights; '
    'from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50, DeepLabV3_ResNet50_Weights; '
    'model = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT); '
    'print(\"DeepLabV3 loaded!\"); '
    'model2 = fcn_resnet50(weights=FCN_ResNet50_Weights.DEFAULT); '
    'print(\"FCN loaded!\")'
'"', timeout=120)
print(out.strip())

c.close()
