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

# 写一个修正的benchmark脚本
script_content = r'''#!/root/miniconda3/bin/python
import sys, time
sys.stdout.reconfigure(line_buffering=True)

import torch
from torchvision.models.segmentation.fcn import fcn_resnet50
from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
import torch.nn as nn

print("TORCH=" + torch.__version__)

# 1. GPU测试
gpu_ok = False
try:
    x = torch.randn(100, 100).cuda()
    torch.cuda.synchronize()
    print("GPU_NAME=" + torch.cuda.get_device_name(0))
    print("GPU_SM=" + str(torch.cuda.get_device_capability(0)))
    gpu_ok = True
except Exception as e:
    print("GPU_ERROR=" + str(e)[:100])

# CPU推理速度测试
def benchmark_cpu(model_fn, name, n_warmup=5, n_run=50):
    try:
        m = model_fn()
        m.eval()
        x = torch.randn(1, 3, 512, 512)
        with torch.no_grad():
            for _ in range(n_warmup): m(x)
        t0 = time.time()
        with torch.no_grad():
            for _ in range(n_run): m(x)
        fps = n_run / (time.time() - t0)
        print(name + "_CPU_FPS=" + str(round(fps, 1)))
        del m
    except Exception as e:
        print(name + "_ERROR=" + str(e)[:100])

# 2. CPU推理速度
print("=== CPU BENCHMARK ===")
benchmark_cpu(fcn_resnet50, "FCN")
benchmark_cpu(deeplabv3_resnet50, "DEEPLABV3")
benchmark_cpu(lrasnet_lowresnet34, "LRASPP")

# 3. GPU推理速度 (如果有兼容GPU)
if gpu_ok:
    print("=== GPU BENCHMARK ===")
    def benchmark_gpu(model_fn, name, n_warmup=5, n_run=100):
        try:
            m = model_fn()
            m = m.cuda()
            m.eval()
            x = torch.randn(1, 3, 512, 512).cuda()
            with torch.no_grad():
                for _ in range(n_warmup): m(x)
                torch.cuda.synchronize()
            t0 = time.time()
            with torch.no_grad():
                for _ in range(n_run): m(x)
                torch.cuda.synchronize()
            fps = n_run / (time.time() - t0)
            print(name + "_GPU_FPS=" + str(round(fps, 1)))
            del m; torch.cuda.empty_cache()
        except Exception as e:
            print(name + "_GPU_ERROR=" + str(e)[:100])

    benchmark_gpu(fcn_resnet50, "FCN")
    benchmark_gpu(deeplabv3_resnet50, "DEEPLABV3")
    benchmark_gpu(lrasnet_lowresnet34, "LRASPP")

    # 4. 批处理
    try:
        m = fcn_resnet50().cuda()
        m.eval()
        x = torch.randn(8, 3, 512, 512).cuda()
        with torch.no_grad():
            for _ in range(5): m(x)
            torch.cuda.synchronize()
        t0 = time.time()
        with torch.no_grad():
            for _ in range(50): m(x)
            torch.cuda.synchronize()
        fps = 400 / (time.time() - t0)
        print("FCN_BATCH8_GPU_FPS=" + str(round(fps, 1)))
    except Exception as e:
        print("BATCH8_GPU_ERROR=" + str(e)[:100])

    # 5. CPU对比批处理
    try:
        m = fcn_resnet50().cpu()
        m.eval()
        x = torch.randn(8, 3, 512, 512)
        with torch.no_grad():
            for _ in range(5): m(x)
        t0 = time.time()
        with torch.no_grad():
            for _ in range(50): m(x)
        fps = 400 / (time.time() - t0)
        print("FCN_BATCH8_CPU_FPS=" + str(round(fps, 1)))
    except Exception as e:
        print("BATCH8_CPU_ERROR=" + str(e)[:100])

print("BENCHMARK_DONE")
'''

sftp = c.open_sftp()
with sftp.open("/root/autodl-tmp/bench_final.py", "w") as f:
    f.write(script_content)
sftp.close()
print("Script written.")

print("\nRunning benchmark...")
stdin, stdout, stderr = c.exec_command(f"{PYTHON} /root/autodl-tmp/bench_final.py 2>/dev/null", timeout=600)
out = stdout.read()
err = stderr.read()
out_str = out.decode('utf-8', errors='replace')
err_str = err.decode('utf-8', errors='replace')

print("Output:")
for line in out_str.split('\n'):
    if line.strip():
        print(f"  {line.strip()}")
print(f"\nErrors (non-warning):")
for line in err_str.split('\n'):
    if line.strip() and 'Warning' not in line and 'warn' not in line.lower():
        print(f"  {line.strip()[:200]}")

c.close()
