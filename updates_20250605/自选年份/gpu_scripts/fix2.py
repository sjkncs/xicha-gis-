#!/usr/bin/env python3
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(10)

def r(c, cmd, timeout=20):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return "ERR:" + str(e)[:80]

# 强制杀掉所有相关进程
print("=== kill ===")
print(r(c, "kill -9 $(ps aux | grep yolo_obstacle | grep -v grep | awk '{print $2}') 2>/dev/null; echo done"))

print("\n=== process check ===")
print(r(c, "ps aux | grep yolo_obstacle | grep -v grep"))

print("\n=== log size ===")
print(r(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== log tail ===")
print(r(c, "cat /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log | tail -30"))

print("\n=== clear log ===")
print(r(c, "truncate -s 0 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== restart (redirect both stdout and stderr) ===")
start = (
    "cd /root/autodl-tmp/streetview_analysis && "
    "python3 -u yolo_obstacle_detect.py > /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log 2>&1 & "
    "echo NEW_PID=$!"
)
print(r(c, start))

time.sleep(10)

print("\n=== log after 10s ===")
print(r(c, "tail -20 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process count ===")
print(r(c, "ps aux | grep yolo_obstacle | grep -v grep"))

c.close()
