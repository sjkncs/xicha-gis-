#!/usr/bin/env python3
"""GPU服务器诊断和基准测试"""
import paramiko, time, sys

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON = "/root/miniconda3/bin/python"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

# === 1. 诊断信息 ===
print("=" * 50)
print("GPU服务器诊断")
print("=" * 50)

def run(cmd, timeout=15):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')
    except Exception as e:
        return "", str(e)

out, err = run("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader")
print(f"GPU: {out.strip()}")

out, err = run(f"{PYTHON} -c \"import torch; print('PyTorch:', torch.__version__, '| CUDA:', torch.version.cuda, '| GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')\"")
print(f"PyTorch: {out.strip()}")

out, err = run("df -h /root /autodl-tmp | tail -3")
print(f"Disk:\n{out}")

# === 2. 写benchmark脚本 ===
bench_script = r"""#!/root/miniconda3/bin/python
import torch, time, os
sys = __import__('sys')

LOG = "/root/autodl-tmp/bench_result.txt"
def log(msg):
    with open(LOG, "a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

log("TORCH=" + torch.__version__)
log("CUDA=" + str(torch.version.cuda))

# GPU测试
try:
    x = torch.randn(100,100).cuda()
    torch.cuda.synchronize()
    log("GPU=OK " + torch.cuda.get_device_name(0))
except Exception as e:
    log("GPU=FAIL " + str(e)[:100])

# 测试1: GPU FCN
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    m = fcn_resnet50().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps = 100 / (time.time() - t0)
    log("FCN_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("FCN_GPU=FAIL " + str(e)[:150])

# 测试2: GPU DeepLabV3
try:
    from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
    m = deeplabv3_resnet50().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps = 100 / (time.time() - t0)
    log("DEEPLABV3_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("DEEPLABV3_GPU=FAIL " + str(e)[:150])

# 测试3: GPU LRASPP (轻量)
try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    m = lrasnet_lowresnet34().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): m(x)
    torch.cuda.synchronize()
    fps = 100 / (time.time() - t0)
    log("LRASPP_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("LRASPP_GPU=FAIL " + str(e)[:150])

# 测试4: GPU 批处理8
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
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
    log("FCN_BATCH8_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("BATCH8_GPU=FAIL " + str(e)[:150])

# 测试5: CPU LRASPP (轻量对比)
try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    m = lrasnet_lowresnet34()
    m.eval()
    x = torch.randn(1, 3, 512, 512)
    with torch.no_grad():
        for _ in range(3): m(x)
    t0 = time.time()
    with torch.no_grad():
        for _ in range(20): m(x)
    fps = 20 / (time.time() - t0)
    log("LRASPP_CPU_FPS=" + str(round(fps, 1)))
    del m
except Exception as e:
    log("LRASPP_CPU=FAIL " + str(e)[:150])

log("BENCHMARK_DONE")
"""

with sftp.open(f"{REMOTE_DIR}/do_bench.py", "w") as f:
    f.write(bench_script)
print(f"\nBenchmark script written to {REMOTE_DIR}/do_bench.py")

# === 3. 后台运行 ===
print("\nStarting benchmark in background...")
# 用shell字符串方式，不等待
channel = c.get_transport().open_session()
channel.exec_command(f"{PYTHON} {REMOTE_DIR}/do_bench.py 2>&1")
# 不等待结果，立刻继续

# 等待60秒
print("Waiting 90 seconds...")
time.sleep(90)

# 读取结果
print("\n=== Benchmark Results ===")
try:
    with sftp.open(f"{REMOTE_DIR}/bench_result.txt") as f:
        result = f.read().decode('utf-8', errors='replace')
    for line in result.strip().split('\n'):
        if line.strip():
            print(f"  {line}")
except FileNotFoundError:
    print("  Result file not found yet (still running)")

sftp.close()
c.close()
print("\nDone!")
