#!/usr/bin/env python3
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace").strip()

# 1. 检查脚本是否已上传
print("=== script uploaded? ===")
run(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_obstacle_detect.py")

# 2. 检查进程
print("\n=== yolo processes ===")
run(c, "ps aux | grep yolo_obstacle | grep -v grep")

# 3. 检查日志
print("\n=== log content ===")
run(c, "cat /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log 2>/dev/null | head -20 || echo 'no log yet'")

# 4. 手动启动
print("\n=== try starting ===")
run(c,
    "cd /root/autodl-tmp/streetview_analysis && "
    "nohup python3 yolo_obstacle_detect.py > yolo_obstacle_run.log 2>&1 & "
    "echo started PID=$!")

c.close()
