#!/usr/bin/env python3
"""测试系统Python (有PyTorch 2.5.1)"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
PYTHON_MINI = "/root/miniconda3/bin/python"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

print("=== 两个Python环境对比 ===")

def test_py(py, name):
    stdin, stdout, stderr = c.exec_command(py + ' -c "import torch; print(\'torch:\', torch.__version__, \'| CUDA:\', torch.version.cuda)"', timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    print(f"\n{name} ({py}):")
    print(f"  {out.strip()}")
    if err.strip(): print(f"  stderr: {err.strip()[:200]}")
    return out.strip()

test_py(PYTHON_MINI, "Miniconda")
test_py(PYTHON_SYS, "System")

# 测试系统Python的GPU
print("\n=== 系统Python GPU测试 ===")
cmd = PYTHON_SYS + ' -c "import torch; x=torch.randn(100,100).cuda(); torch.cuda.synchronize(); print(\'GPU OK:\', torch.cuda.get_device_name(0))" 2>&1'
stdin, stdout, stderr = c.exec_command(cmd, timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print(f"GPU test: {out.strip()}")
if err.strip(): print(f"  stderr: {err.strip()[:300]}")

# GPU Conv测试
print("\n=== GPU Conv基准 ===")
conv_test = r"""#!/usr/bin/python3
import torch, time

LOG = "/root/autodl-tmp/sys_gpu_result.txt"
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

with sftp.open(REMOTE_DIR + "/sys_gpu_conv.py", "w") as f:
    f.write(conv_test)

channel = c.get_transport().open_session()
channel.exec_command(PYTHON_SYS + " " + REMOTE_DIR + "/sys_gpu_conv.py 2>&1")

print("Running GPU test, waiting 60s...")
time.sleep(60)

try:
    with sftp.open(REMOTE_DIR + "/sys_gpu_result.txt") as f:
        print(f.read().decode())
except FileNotFoundError:
    print("  (still running)")

sftp.close()
c.close()
