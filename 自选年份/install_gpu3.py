#!/usr/bin/env python3
"""后台安装脚本 - 解决超时问题"""
import paramiko, time, sys
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

print("=" * 60)
print("安装 PyTorch (pip + 清华镜像)")
print("=" * 60)
c = ssh()

# 先清理之前的进程
run(c, "pkill -f 'conda install' 2>/dev/null; pkill -f 'pip install' 2>/dev/null; echo 'cleaned'")

# pip 安装 PyTorch (清华镜像)
print("Starting pip install (background)...")
run(c, "pip3 install torch torchvision --index-url https://pypi.tuna.tsinghua.edu.cn/simple -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | tee /root/autodl-tmp/install_pytorch.log &", timeout=5)

print("Install started in background. PID check:")
run(c, "ps aux | grep 'pip install' | grep -v grep | head -5")
run(c, "cat /root/autodl-tmp/install_pytorch.log 2>/dev/null | tail -3 || echo 'log not yet'")

# 等待一会儿看进度
time.sleep(10)
run(c, "cat /root/autodl-tmp/install_pytorch.log 2>/dev/null | tail -5")

c.close()
print("\n安装已在后台启动，可手动检查进度:")
print("  ssh -p 37625 root@connect.bjb1.seetacloud.com")
print("  tail -f /root/autodl-tmp/install_pytorch.log")
print("  python3 -c 'import torch; print(torch.__version__)'")
