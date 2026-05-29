#!/usr/bin/env python3
"""持续监控PyTorch安装直到完成"""
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

print("=== 检查当前状态 ===")
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; print('version:', torch.__version__, '| CUDA:', torch.version.cuda)\"", timeout=15)
print(stdout.read().decode().strip())

# 检查安装是否已经在运行
stdin, stdout, stderr = c.exec_command("ps aux | grep pip3 | grep -v grep", timeout=10)
print(f"PIP3 processes: {stdout.read().decode().strip()[:200]}")

# 检查日志末尾
stdin, stdout, stderr = c.exec_command(f"tail -5 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
log = stdout.read().decode('utf-8', errors='replace')
print(f"Install log: {log.strip()[:200]}")

# 如果pip已经在跑，直接监控
if b'pip3' in stdout.read():
    print("\n=== 安装进行中，监控进度 ===")
else:
    print("\n=== 启动安装 ===")
    c.exec_command("killall pip3 pip 2>/dev/null; sleep 1")
    install_cmd = f"pip3 install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 600 >> {REMOTE_DIR}/pytorch_install.log 2>&1 &"
    c.exec_command(install_cmd, timeout=10)
    print("Install started")

# 监控循环
print("\n=== 监控安装进度 ===")
last_line = ""
stable_count = 0

for i in range(20):  # 最多20轮，每轮45秒 = 最多15分钟
    time.sleep(45)

    # 检查pip进程
    stdin, stdout, stderr = c.exec_command("pgrep -f 'pip3 install' | head -1", timeout=10)
    pip_pid = stdout.read().decode().strip()

    # 检查日志
    stdin, stdout, stderr = c.exec_command(f"tail -1 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
    line = stdout.read().decode('utf-8', errors='replace').strip()

    # 检查PyTorch版本
    stdin2, stdout2, stderr2 = c.exec_command(f"{PYTHON} -c \"import torch; print(torch.__version__)\"", timeout=15)
    version = stdout2.read().decode().strip()

    download_mb = ""
    stdin3, stdout3, stderr3 = c.exec_command(f"grep 'Downloading' {REMOTE_DIR}/pytorch_install.log 2>/dev/null | tail -1", timeout=10)
    dl = stdout3.read().decode('utf-8', errors='replace').strip()
    if dl:
        download_mb = dl[:60]

    print(f"  [{i+1}] t+{(i+1)*45}s | pip: {pip_pid or 'DONE':10} | torch: {version:15} | {download_mb}")

    # 检测安装完成
    if 'INSTALL_DONE' in line or 'Successfully installed' in line:
        print(f"\n=== 安装完成信号: {line} ===")
        break
    if 'ERROR' in line or 'ERROR' in last_line:
        print(f"\n=== 安装出错 ===")
        break
    if line == last_line and not pip_pid:
        stable_count += 1
        if stable_count >= 2:
            print(f"\n=== 安装似乎已完成（稳定）===")
            break
    else:
        stable_count = 0
    last_line = line

# 最终检查
print("\n=== 最终状态 ===")
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; print('torch:', torch.__version__, '| CUDA:', torch.version.cuda, '| cuDNN:', torch.backends.cudnn.version())\"", timeout=15)
print(stdout.read().decode().strip())

stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; x=torch.randn(100,100).cuda(); print('GPU:', torch.cuda.get_device_name(0))\" 2>&1", timeout=15)
out = stdout.read().decode('utf-8', errors='replace')
print(f"GPU test: {out.strip()[:200]}")

stdin, stdout, stderr = c.exec_command(f"tail -15 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
print(f"\n=== 安装日志 ===\n{stdout.read().decode('utf-8', errors='replace')}")

sftp.close()
c.close()
