#!/usr/bin/env python3
"""重新上传脚本并用 python3 启动"""
import paramiko, time, os

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp"

SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\gpu_full_render.py"
FONT_LOCAL = r"e:\xicha gis 智能定位\自选年份\NotoSansCJK.otf"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = ssh.open_sftp()

# 上传脚本
print("[1/2] 上传脚本...")
sftp.put(SCRIPT_LOCAL, f"{REMOTE_BASE}/gpu_full_render.py")
print("  脚本上传完成")

# 上传字体（确保存在）
print("[2/2] 上传字体...")
sftp.put(FONT_LOCAL, f"{REMOTE_BASE}/NotoSansCJK.otf")
print("  字体上传完成")

sftp.close()

# 清理旧进程
def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

ssh.exec_command("pkill -9 -f gpu_full_render 2>/dev/null; rm -f /root/autodl-tmp/full_render.log /root/autodl-tmp/full_render.pid", timeout=10)

# 启动
print("\n[启动] 后台运行全量渲染...")
start_cmd = (
    "cd /root/autodl-tmp && "
    "nohup python3 gpu_full_render.py > full_render.log 2>&1 & "
    "echo $! > full_render.pid && "
    "echo PID:$(cat full_render.pid):STARTED"
)
out, err = run(start_cmd)
print(f"  {out.strip()}")
if err.strip():
    print(f"  stderr: {err[:100]}")

time.sleep(10)

# 验证
out, _ = run("ps aux | grep gpu_full_render | grep -v grep")
print(f"\n[进程]\n{out if out.strip() else '  (未运行)'}")

out, _ = run("tail -15 /root/autodl-tmp/full_render.log")
print(f"\n[日志]\n{out if out.strip() else '  (暂无)'}")

ssh.close()
print("\n完成!")
