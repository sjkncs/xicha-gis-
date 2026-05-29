#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
PYTHON = "/root/miniconda3/bin/python"

# 先检查已有的模型
print("=== 已有数据 ===")
stdin, stdout, stderr = c.exec_command("ls /root/autodl-tmp/ 2>/dev/null | head -20")
print(stdout.read().decode())

stdin, stdout, stderr = c.exec_command("df -h /root /autodl-tmp / | tail -5")
print(stdout.read().decode())

stdin, stdout, stderr = c.exec_command("find /root/autodl-tmp/ -name '*.jpg' -o -name '*.png' -o -name '*.pth' 2>/dev/null | head -20")
print(stdout.read().decode())

# 写benchmark脚本
script = r'''#!/root/miniconda3/bin/python
import torch, time, sys
sys.stdout = open("/root/autodl-tmp/bench.log", "w")
sys.stderr = open("/root/autodl-tmp/bench_err.log", "w")
sys.stdout.write("TORCH=" + torch.__version__ + "\n")
sys.stdout.flush()

try:
    x = torch.randn(100,100).cuda()
    torch.cuda.synchronize()
    sys.stdout.write("GPU=OK " + torch.cuda.get_device_name(0) + "\n")
    sys.stdout.flush()
except Exception as e:
    sys.stdout.write("GPU=FAIL " + str(e) + "\n")
    sys.stdout.flush()

from torchvision.models.segmentation.fcn import fcn_resnet50
from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34

# GPU FCN
try:
    m = fcn_resnet50().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    for _ in range(5):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(100):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    sys.stdout.write("FCN_GPU_FPS=" + str(round(100/(time.time()-t0), 1)) + "\n")
    sys.stdout.flush()
    del m; torch.cuda.empty_cache()
except Exception as e:
    sys.stdout.write("FCN_GPU=FAIL " + str(e)[:200] + "\n")
    sys.stdout.flush()

# GPU DeepLabV3
try:
    m = deeplabv3_resnet50().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    for _ in range(5):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(100):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    sys.stdout.write("DEEPLABV3_GPU_FPS=" + str(round(100/(time.time()-t0), 1)) + "\n")
    sys.stdout.flush()
    del m; torch.cuda.empty_cache()
except Exception as e:
    sys.stdout.write("DEEPLABV3_GPU=FAIL " + str(e)[:200] + "\n")
    sys.stdout.flush()

# GPU LRASPP
try:
    m = lrasnet_lowresnet34().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    for _ in range(5):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(100):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    sys.stdout.write("LRASPP_GPU_FPS=" + str(round(100/(time.time()-t0), 1)) + "\n")
    sys.stdout.flush()
    del m; torch.cuda.empty_cache()
except Exception as e:
    sys.stdout.write("LRASPP_GPU=FAIL " + str(e)[:200] + "\n")
    sys.stdout.flush()

# GPU 批处理
try:
    m = fcn_resnet50().cuda()
    m.eval()
    x = torch.randn(8, 3, 512, 512).cuda()
    for _ in range(5):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(50):
        with torch.no_grad(): r = m(x)
    torch.cuda.synchronize()
    sys.stdout.write("FCN_BATCH8_GPU_FPS=" + str(round(400/(time.time()-t0), 1)) + "\n")
    sys.stdout.flush()
    del m; torch.cuda.empty_cache()
except Exception as e:
    sys.stdout.write("BATCH8_GPU=FAIL " + str(e)[:200] + "\n")
    sys.stdout.flush()

# CPU LRASPP (轻量模型对比)
try:
    m = lrasnet_lowresnet34()
    m.eval()
    x = torch.randn(1, 3, 512, 512)
    for _ in range(3):
        with torch.no_grad(): r = m(x)
    t0 = time.time()
    for _ in range(20):
        with torch.no_grad(): r = m(x)
    sys.stdout.write("LRASPP_CPU_FPS=" + str(round(20/(time.time()-t0), 1)) + "\n")
    sys.stdout.flush()
    del m
except Exception as e:
    sys.stdout.write("LRASPP_CPU=FAIL " + str(e)[:200] + "\n")
    sys.stdout.flush()

sys.stdout.write("BENCHMARK_DONE\n")
sys.stdout.flush()
'''

sftp = c.open_sftp()
with sftp.open("/root/autodl-tmp/bench_gpu.py", "w") as f:
    f.write(script)
sftp.close()

# 后台运行
stdin, stdout, stderr = c.exec_command(
    f"cd /root/autodl-tmp && nohup {PYTHON} bench_gpu.py > bench_nohup.log 2>&1 &",
    timeout=10
)
print("PID:", stdout.read().decode().strip())

# 等60秒
print("\nWaiting 60s for benchmark to complete...")
time.sleep(60)

# 读取结果
stdin, stdout, stderr = c.exec_command("cat /root/autodl-tmp/bench.log 2>/dev/null")
out = stdout.read().decode('utf-8', errors='replace')
print("\n=== Benchmark Results ===")
for line in out.split('\n'):
    if line.strip():
        print(f"  {line.strip()}")

stdin, stdout, stderr = c.exec_command("cat /root/autodl-tmp/bench_err.log 2>/dev/null | head -5")
err = stdout.read().decode('utf-8', errors='replace')
if err.strip():
    print(f"\nErrors: {err.strip()[:300]}")

c.close()
