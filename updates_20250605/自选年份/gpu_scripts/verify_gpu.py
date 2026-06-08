#!/usr/bin/env python3
"""验证PyTorch 2.5.1并运行GPU基准测试"""
import paramiko, time

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

print("=== PyTorch 2.5.1 验证 ===")

# 测试新版本
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; print('Version:', torch.__version__); print('CUDA:', torch.version.cuda)\" 2>&1", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(f"stdout: {out.strip()}")
print(f"stderr (warnings): {err.strip()[:200]}")

# 测试GPU
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; x=torch.randn(100,100).cuda(); torch.cuda.synchronize(); print('GPU:', torch.cuda.get_device_name(0))\" 2>&1", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(f"GPU: {out.strip()}")
if 'not compatible' in err or 'sm_120' in err:
    print("  WARNING: Still seeing sm_120 warning - need to check")
else:
    print("  No CUDA warnings!")

# GPU卷积测试
print("\n=== GPU卷积基准测试 ===")
test_conv = r"""#!/root/miniconda3/bin/python
import torch, time, sys

LOG = "/root/autodl-tmp/gpu_conv_result.txt"
def log(msg):
    with open(LOG, "a") as f: f.write(msg + "\n")
    print(msg, flush=True)

log("TORCH=" + torch.__version__)
log("CUDA=" + str(torch.version.cuda))

try:
    conv = torch.nn.Conv2d(3, 64, 3, padding=1).cuda()
    x = torch.randn(8, 3, 512, 512).cuda()
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(100):
        r = conv(x)
        torch.cuda.synchronize()
    fps = 800 / (time.time() - t0)
    log("GPU_CONV_BATCH8_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("GPU_CONV_FAIL=" + str(e)[:200])

try:
    conv = torch.nn.Conv2d(3, 64, 3, padding=1).cuda()
    x = torch.randn(1, 3, 512, 512).cuda()
    torch.cuda.synchronize()
    t0 = time.time()
    for _ in range(200):
        r = conv(x)
        torch.cuda.synchronize()
    fps = 200 / (time.time() - t0)
    log("GPU_CONV_SINGLE_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("GPU_CONV_FAIL=" + str(e)[:200])

log("DONE")
"""

with sftp.open(f"{REMOTE_DIR}/gpu_conv.py", "w") as f:
    f.write(test_conv)

channel = c.get_transport().open_session()
channel.exec_command(f"{PYTHON} {REMOTE_DIR}/gpu_conv.py 2>&1")

print("GPU conv test running, waiting 60s...")
time.sleep(60)

try:
    with sftp.open(f"{REMOTE_DIR}/gpu_conv_result.txt") as f:
        print(f.read().decode())
except FileNotFoundError:
    print("  (still running)")

# GPU分割模型测试
print("\n=== GPU分割模型测试 ===")
test_seg = r"""#!/root/miniconda3/bin/python
import torch, time, sys

LOG = "/root/autodl-tmp/gpu_seg_result.txt"
def log(msg):
    with open(LOG, "a") as f: f.write(msg + "\n")
    print(msg, flush=True)

log("TORCH=" + torch.__version__)

try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    m = fcn_resnet50().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 50 / (time.time() - t0)
    log("FCN_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("FCN_GPU_FAIL=" + str(e)[:200])

try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34
    m = lrasnet_lowresnet34().cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 50 / (time.time() - t0)
    log("LRASPP_GPU_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("LRASPP_GPU_FAIL=" + str(e)[:200])

log("DONE")
"""

with sftp.open(f"{REMOTE_DIR}/gpu_seg.py", "w") as f:
    f.write(test_seg)

channel2 = c.get_transport().open_session()
channel2.exec_command(f"{PYTHON} {REMOTE_DIR}/gpu_seg.py 2>&1")

print("GPU seg test running, waiting 120s...")
time.sleep(120)

try:
    with sftp.open(f"{REMOTE_DIR}/gpu_seg_result.txt") as f:
        print(f.read().decode())
except FileNotFoundError:
    print("  (still running)")

sftp.close()
c.close()
print("\nAll done!")
