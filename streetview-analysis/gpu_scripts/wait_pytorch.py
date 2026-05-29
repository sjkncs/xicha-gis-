#!/usr/bin/env python3
"""清理后台进程 + 等待PyTorch安装完成"""
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

# 1. 杀掉所有之前的后台测试进程
print("=== 清理后台进程 ===")
kill_cmds = [
    "kill -9 4991 4992 5850 5851 2>/dev/null; echo done",
    "ps aux | grep -E 'bench|seg_test|do_bench' | grep -v grep",
]
for cmd in kill_cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace')
    if cmd.startswith("ps"):
        print(f"Remaining: {out.strip() or 'clean'}")
    else:
        print(f"Kill: {out.strip()}")

# 2. 检查PyTorch安装进度
print("\n=== PyTorch安装进度 ===")
stdin, stdout, stderr = c.exec_command(f"tail -10 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
print(stdout.read().decode())

# 3. 检查pip进程
stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip install' | grep -v grep", timeout=10)
pip_status = stdout.read().decode()
print(f"PIP process: {'RUNNING' if 'pip' in pip_status else 'DONE/STOPPED'}")
print(pip_status.strip()[:200])

# 4. 等待安装完成（最多等待5分钟，每30秒检查一次）
print("\n=== 等待PyTorch安装完成 ===")
max_wait = 300
interval = 30
elapsed = 0

while elapsed < max_wait:
    time.sleep(interval)
    elapsed += interval

    # 检查pip进程
    stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip install' | grep -v grep", timeout=10)
    pip_running = b'pip' in stdout.read()

    # 检查安装日志
    stdin, stdout, stderr = c.exec_command(f"tail -5 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
    log = stdout.read().decode('utf-8', errors='replace')

    # 检查新PyTorch是否可用
    stdin2, stdout2, stderr2 = c.exec_command(f"{PYTHON} -c \"import torch; print(torch.__version__)\"", timeout=15)
    version = stdout2.read().decode().strip()

    print(f"  t+{elapsed}s | pip: {'YES' if pip_running else 'NO '} | log: {log.strip()[:80]}")
    print(f"            | version: {version}")

    if not pip_running and '2.5' in version:
        print("\n=== PyTorch 2.5.x 安装成功！===")
        break

    if not pip_running and '2.1' in version:
        print("\n=== 旧版PyTorch, 安装可能失败 ===")
        stdin, stdout, stderr = c.exec_command(f"tail -20 {REMOTE_DIR}/pytorch_install.log 2>/dev/null", timeout=10)
        print(stdout.read().decode())
        break

sftp.close()
c.close()
print("\n检查完成!")
