#!/usr/bin/env python3
"""检查 GPU python 环境并启动"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode("utf-8", errors="replace")

# 1. 找 python
print("=== Python 环境 ===")
out = run("which python3 python 2>/dev/null; python3 --version 2>/dev/null; python --version 2>/dev/null")
print(out or "(无 python)")

# 2. 检查字体文件
print("\n=== 字体文件 ===")
out = run("ls -lh /root/autodl-tmp/NotoSansCJK.otf 2>/dev/null")
print(out or "(未找到)")

# 3. 清理旧进程和日志
run("pkill -f gpu_full_render 2>/dev/null; rm -f /root/autodl-tmp/full_render.log /root/autodl-tmp/full_render.pid")

# 4. 启动（用 python3）
PYTHON = "python3"
start_cmd = (
    f"cd /root/autodl-tmp && "
    f"nohup {PYTHON} gpu_full_render.py > full_render.log 2>&1 & "
    f"echo $! > full_render.pid && "
    f"cat full_render.pid && "
    f"echo '---STARTED---'"
)
stdin, stdout, stderr = ssh.exec_command(start_cmd, timeout=30)
output = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(f"\n启动输出:\n{output}")
if err.strip():
    print(f"错误:\n{err}")

time.sleep(8)

# 5. 确认运行
print("\n=== 进程状态 ===")
out = run("ps aux | grep gpu_full_render | grep -v grep")
print(out if out.strip() else "(未运行)")

print("\n=== 最新日志 ===")
out = run("tail -10 /root/autodl-tmp/full_render.log")
print(out if out.strip() else "(暂无日志)")

ssh.close()
print("\nGPU 全量推理已启动!")
