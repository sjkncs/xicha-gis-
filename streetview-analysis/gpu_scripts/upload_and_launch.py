#!/usr/bin/env python3
"""上传字体+脚本到 GPU 并启动全量渲染"""
import paramiko, os

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

FONT_LOCAL = r"e:\xicha gis 智能定位\自选年份\NotoSansCJK.otf"
SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\gpu_full_render.py"
REMOTE_BASE = "/root/autodl-tmp"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = ssh.open_sftp()

print("=== 上传字体 ===")
sftp.put(FONT_LOCAL, f"{REMOTE_BASE}/NotoSansCJK.otf")
st = sftp.stat(f"{REMOTE_BASE}/NotoSansCJK.otf")
print(f"字体已上传: {st.st_size/1024/1024:.1f} MB")

print("\n=== 上传脚本 ===")
sftp.put(SCRIPT_LOCAL, f"{REMOTE_BASE}/gpu_full_render.py")
st = sftp.stat(f"{REMOTE_BASE}/gpu_full_render.py")
print(f"脚本已上传: {st.st_size} bytes")

sftp.close()

# 启动 GPU 推理（后台 nohup）
print("\n=== 启动 GPU 全量推理 ===")
start_cmd = (
    f"cd /root/autodl-tmp && "
    f"nohup python gpu_full_render.py > full_render.log 2>&1 & "
    f"echo $! > full_render.pid && "
    f"cat full_render.pid"
)
stdin, stdout, stderr = ssh.exec_command(start_cmd, timeout=30)
pid = stdout.read().decode("utf-8", errors="replace").strip()
print(f"进程 PID: {pid}")

# 等待 5 秒，确认启动成功
import time
time.sleep(5)

stdin, stdout, stderr = ssh.exec_command("ps aux | grep gpu_full_render | grep -v grep", timeout=10)
running = stdout.read().decode("utf-8", errors="replace")
print(f"\n进程状态:\n{running if running.strip() else '(未找到进程，检查日志)'}")

stdin, stdout, stderr = ssh.exec_command("tail -5 /root/autodl-tmp/full_render.log 2>/dev/null", timeout=10)
log = stdout.read().decode("utf-8", errors="replace")
print(f"\n最近日志:\n{log if log.strip() else '(暂无)'}")

ssh.close()
print("\n=== 启动完成 ===")
print("监控命令: tail -f /root/autodl-tmp/full_render.log")
print("停止命令: kill $(cat /root/autodl-tmp/full_render.pid)")
