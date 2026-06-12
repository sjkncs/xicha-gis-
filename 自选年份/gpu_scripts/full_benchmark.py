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

# 直接在服务器写一个完整的推理测试脚本
script_content = r'''#!/root/miniconda3/bin/python
import sys, time
sys.stdout.reconfigure(line_buffering=True)

# 1. GPU基础测试
import torch
print("TORCH_VERSION=" + torch.__version__)
print("CUDA_AVAILABLE=" + str(torch.cuda.is_available()))
if torch.cuda.is_available():
    print("GPU_NAME=" + torch.cuda.get_device_name(0))
    print("GPU_SM=" + str(torch.cuda.get_device_capability(0)))

    # 2. 推理测试 - 无预训练权重
    from torchvision.models.segmentation.fcn import fcn_resnet50
    import torch.nn as nn
    m = fcn_resnet50()
    # 修改为21类Cityscapes
    m.classifier[4] = nn.Conv2d(512, 21, bias=True)
    m = m.cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5):
            r = m(x)
        torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50):
            r = m(x)
        torch.cuda.synchronize()
    fps = 50 / (time.time() - t0)
    print("FCN_SINGLE_FPS=" + str(round(fps, 1)))

    # 3. 批处理测试
    x = torch.randn(4, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5):
            r = m(x)
        torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50):
            r = m(x)
        torch.cuda.synchronize()
    fps = 200 / (time.time() - t0)
    print("FCN_BATCH4_FPS=" + str(round(fps, 1)))

    # 4. DeepLabV3测试
    from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
    m2 = deeplabv3_resnet50()
    m2.classifier[4] = nn.Conv2d(256, 21, bias=True)
    m2 = m2.cuda()
    m2.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5):
            r = m2(x)
        torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50):
            r = m2(x)
        torch.cuda.synchronize()
    fps2 = 50 / (time.time() - t0)
    print("DEEPLABV3_SINGLE_FPS=" + str(round(fps2, 1)))

    # 5. LR-ASPP测试 (更快)
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    m3 = lrasnet_lowresnet34()
    m3.segmentation_head[2] = nn.Conv2d(32, 21, bias=True)
    m3 = m3.cuda()
    m3.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5):
            r = m3(x)
        torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100):
            r = m3(x)
        torch.cuda.synchronize()
    fps3 = 100 / (time.time() - t0)
    print("LRASPP_SINGLE_FPS=" + str(round(fps3, 1)))

print("BENCHMARK_DONE")
'''

# 写入文件
sftp = c.open_sftp()
with sftp.open("/root/autodl-tmp/benchmark_gpu.py", "w") as f:
    f.write(script_content)
sftp.close()
print("Script written.")

# 执行benchmark
print("\nRunning benchmark...")
import time as _time
stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/benchmark_gpu.py", timeout=300)
out = stdout.read()
err = stderr.read()
print(f"stdout ({len(out)} bytes):")
for line in out.decode('utf-8', errors='replace').split('\n'):
    if line.strip():
        print(f"  {line.strip()}")
print(f"stderr ({len(err)} bytes):")
for line in err.decode('utf-8', errors='replace').split('\n'):
    if line.strip() and 'UserWarning' not in line:
        print(f"  {line.strip()[:200]}")

c.close()
