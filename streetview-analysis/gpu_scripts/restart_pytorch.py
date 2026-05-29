#!/usr/bin/env python3
"""重新启动PyTorch安装并等待完成"""
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

# 1. 检查pip是否还在运行
stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip install' | grep -v grep", timeout=10)
pip_running = len(stdout.read().strip()) > 0
print(f"PIP running: {pip_running}")

# 2. 检查当前PyTorch版本
stdin, stdout, stderr = c.exec_command(f"{PYTHON} -c \"import torch; print('version:', torch.__version__)\"", timeout=15)
print(f"Current version: {stdout.read().decode().strip()}")

# 3. 如果pip不在运行，重新启动安装
if not pip_running:
    print("\n=== 重新启动PyTorch 2.5.1安装 ===")
    # 先杀掉pip进程（如果存在残留）
    c.exec_command("killall pip3 pip 2>/dev/null; echo killed")
    time.sleep(2)

    # 写安装脚本
    install_script = r"""#!/bin/bash
pip3 install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 600 >> /root/autodl-tmp/pytorch_install.log 2>&1
echo "EXIT_CODE=$?" >> /root/autodl-tmp/pytorch_install.log
echo "INSTALL_DONE" >> /root/autodl-tmp/pytorch_install.log
"""
    with sftp.open(f"{REMOTE_DIR}/install_pytorch.sh", "w") as f:
        f.write(install_script)

    # 启动安装
    stdin, stdout, stderr = c.exec_command(f"cd /root/autodl-tmp && bash install_pytorch.sh &", timeout=10)
    print(f"Install started in background")

    # 等几秒检查进程
    time.sleep(10)
    stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip install' | grep -v grep", timeout=10)
    print(f"PIP running: {len(stdout.read().strip()) > 0}")

# 4. 等待安装完成（最多10分钟）
print("\n=== 等待安装完成 ===")
max_wait = 600
interval = 45
elapsed = 0

while elapsed < max_wait:
    time.sleep(interval)
    elapsed += interval

    stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip install' | grep -v grep", timeout=10)
    pip_running = len(stdout.read().strip()) > 0

    stdin, stdout, stderr = c.exec_command(f"tail -3 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
    log_tail = stdout.read().decode('utf-8', errors='replace')

    stdin2, stdout2, stderr2 = c.exec_command(f"{PYTHON} -c \"import torch; print(torch.__version__)\"", timeout=15)
    version = stdout2.read().decode().strip()

    print(f"  t+{elapsed}s | pip: {'YES' if pip_running else 'NO '} | {version} | {log_tail.strip()[:60]}")

    if not pip_running:
        # 检查是否真的安装成功了
        stdin3, stdout3, stderr3 = c.exec_command(f"{PYTHON} -c \"import torch; print('OK', torch.__version__, torch.version.cuda)\"", timeout=15)
        result = stdout3.read().decode().strip()
        print(f"\n  Final: {result}")
        if '2.5' in result:
            print("\n=== PyTorch 2.5.x 安装成功! ===")
            break
        elif '2.1' in result:
            print("\n=== 仍为2.1版, 安装可能失败 ===")
            break

print("\n=== 安装日志末尾 ===")
stdin, stdout, stderr = c.exec_command(f"tail -20 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
print(stdout.read().decode())

sftp.close()
c.close()
