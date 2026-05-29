#!/usr/bin/env python3
import paramiko, socket

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(10)

def run_quick(c, cmd, timeout=15):
    """快速命令，收不到输出也继续"""
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except (socket.timeout, EOFError, TimeoutError):
        return ""

print("=== 1. check if script uploaded ===")
print(run_quick(c, "timeout 5 ls -lh /root/autodl-tmp/streetview_analysis/yolo_obstacle_detect.py"))

print("\n=== 2. check if already running ===")
print(run_quick(c, "timeout 5 ps aux | grep yolo_obstacle | grep -v grep"))

print("\n=== 3. check log ===")
print(run_quick(c, "timeout 5 cat /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log 2>/dev/null | tail -10 || echo 'no log'"))

print("\n=== 4. start detection (timeout-wrapped) ===")
# 用 timeout 确保立即返回，不等后台进程
start_cmd = (
    "timeout 10 bash -c '"
    "cd /root/autodl-tmp/streetview_analysis && "
    "nohup python3 yolo_obstacle_detect.py > yolo_obstacle_run.log 2>&1 & "
    "echo STARTED PID=$!"
    "'"
)
result = run_quick(c, start_cmd)
print("START RESULT:", result)

print("\n=== 5. verify process started ===")
print(run_quick(c, "timeout 5 ps aux | grep yolo_obstacle | grep -v grep"))

print("\n=== 6. check initial log ===")
print(run_quick(c, "timeout 5 head -5 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log 2>/dev/null || echo 'log empty'"))

c.close()
print("\ndone")
