#!/usr/bin/env python3
"""安装PyTorch 2.12 nightly + 测试GPU"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

# 1. 写安装脚本
install_script = r"""#!/bin/bash
pip3 uninstall torch torchvision -y >> /root/autodl-tmp/pip212.log 2>&1
pip3 install torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu124 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 600 >> /root/autodl-tmp/pip212.log 2>&1
echo "INSTALL_212_EXIT=$?" >> /root/autodl-tmp/pip212.log
echo "INSTALL_212_DONE" >> /root/autodl-tmp/pip212.log
"""

with sftp.open(REMOTE_DIR + "/install_212.sh", "w") as f:
    f.write(install_script)

print("=== 启动PyTorch 2.12安装 ===")
# 杀掉现有pip进程
c.exec_command("pkill -f 'pip3 install' 2>/dev/null; sleep 1; echo killed")
time.sleep(2)

# 启动安装
channel = c.get_transport().open_session()
channel.exec_command("bash " + REMOTE_DIR + "/install_212.sh 2>&1 &")
print("Install started in background")

# 等待安装（最多15分钟）
print("Waiting for install to start...")
time.sleep(30)

# 检查进度
print("\n=== 监控安装进度 ===")
for i in range(30):  # 最多15分钟
    time.sleep(30)

    stdin, stdout, stderr = c.exec_command("tail -3 /root/autodl-tmp/pip212.log 2>/dev/null", timeout=10)
    log = stdout.read().decode('utf-8', errors='replace').strip()

    stdin2, stdout2, stderr2 = c.exec_command("pgrep -f 'pip3' | head -1", timeout=10)
    pip_pid = stdout2.read().decode().strip()

    stdin3, stdout3, stderr3 = c.exec_command(PYTHON_SYS + " -c \"import torch; print(torch.__version__)\" 2>/dev/null", timeout=10)
    ver = stdout3.read().decode().strip()

    print(f"  [{i+1}] t+{(i+1)*30}s | pip: {pip_pid or 'DONE':6} | torch: {ver:12} | {log[:60]}")

    if 'INSTALL_212_DONE' in log:
        print("\n=== 安装完成 ===")
        break
    if 'INSTALL_212_EXIT=0' in log and not pip_pid:
        break

# 最终验证
print("\n=== PyTorch 2.12验证 ===")
stdin, stdout, stderr = c.exec_command(PYTHON_SYS + " -c \"import torch; print('torch:', torch.__version__, '| CUDA:', torch.version.cuda)\" 2>&1", timeout=15)
print(stdout.read().decode().strip())

# GPU测试
print("\n=== GPU卷积测试 ===")
gpu_test = r"""#!/usr/bin/python3
import torch, time

LOG = "/root/autodl-tmp/gpu212_result.txt"
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

with sftp.open(REMOTE_DIR + "/gpu212_conv.py", "w") as f:
    f.write(gpu_test)

channel2 = c.get_transport().open_session()
channel2.exec_command(PYTHON_SYS + " " + REMOTE_DIR + "/gpu212_conv.py 2>&1")

print("Running GPU test, waiting 60s...")
time.sleep(60)

try:
    with sftp.open(REMOTE_DIR + "/gpu212_result.txt") as f:
        result = f.read().decode()
        print(result)
        if 'GPU_CONV_FAIL' in result and 'no kernel image' in result:
            print("\n  sm_120 still not supported in 2.12 nightly")
except FileNotFoundError:
    print("  (still running)")

# 打印安装日志
print("\n=== 安装日志 ===")
stdin, stdout, stderr = c.exec_command("tail -30 /root/autodl-tmp/pip212.log 2>/dev/null", timeout=10)
print(stdout.read().decode('utf-8', errors='replace'))

sftp.close()
c.close()
