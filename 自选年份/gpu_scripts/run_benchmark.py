#!/usr/bin/env python3
import paramiko
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

# 在服务器上写GPU速度测试脚本
script = r'''#!/root/miniconda3/bin/python
import torch, time, json, sys
sys.stdout.reconfigure(line_buffering=True)

# GPU测试
try:
    x = torch.randn(1000, 1000).cuda()
    gpu_name = torch.cuda.get_device_name(0)
    print(f"GPU_NAME={gpu_name}")
    print(f"SUM={x.sum().item():.2f}")
except Exception as e:
    print(f"GPU_ERROR={e}")

# FCN GPU速度
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    import torch.nn as nn
    m = fcn_resnet50()
    m.classifier[4] = nn.Conv2d(512, 21, bias=True)
    m = m.cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(10): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps_fcn = 100 / (time.time() - t0)
    print(f"FCN_GPU_FPS={fps_fcn:.1f}")
except Exception as e:
    print(f"FCN_ERROR={e}")

# DeepLabV3 GPU速度
try:
    from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
    import torch.nn as nn
    m = deeplabv3_resnet50()
    m.classifier[4] = nn.Conv2d(256, 21, bias=True)
    m = m.cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(10): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps_dlv3 = 100 / (time.time() - t0)
    print(f"DEEPLABV3_GPU_FPS={fps_dlv3:.1f}")
except Exception as e:
    print(f"DEEPLABV3_ERROR={e}")

# LR-ASPP GPU速度
try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    import torch.nn as nn
    m = lrasnet_lowresnet34()
    m.segmentation_head[2] = nn.Conv2d(32, 21, bias=True)
    m = m.cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(10): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps_lra = 100 / (time.time() - t0)
    print(f"LRASPP_GPU_FPS={fps_lra:.1f}")
except Exception as e:
    print(f"LRASPP_ERROR={e}")

# 批处理速度 (batch=8)
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    import torch.nn as nn
    m = fcn_resnet50()
    m.classifier[4] = nn.Conv2d(512, 21, bias=True)
    m = m.cuda()
    m.eval()
    x = torch.randn(8, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(10): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50): m(x)
    torch.cuda.synchronize()
    fps_batch = 400 / (time.time() - t0)
    print(f"FCN_BATCH8_FPS={fps_batch:.1f}")
except Exception as e:
    print(f"BATCH8_ERROR={e}")

print("BENCHMARK_DONE")
'''

# 写入文件
sftp = c.open_sftp()
with sftp.open("/root/autodl-tmp/gpu_benchmark.py", "w") as f:
    f.write(script)
sftp.close()
print("Benchmark script written.")

# 执行
print("\nRunning GPU benchmark...")
import time
stdin, stdout, stderr = c.exec_command("/root/miniconda3/bin/python /root/autodl-tmp/gpu_benchmark.py", timeout=600)
# 分行读取输出
out_lines = []
while True:
    try:
        line = stdout.readline()
        if not line:
            break
        line = line.decode('utf-8', errors='replace').strip()
        if line:
            out_lines.append(line)
            print(f"  {line}")
    except:
        break

print(f"\nBenchmark complete! Got {len(out_lines)} lines.")
c.close()
