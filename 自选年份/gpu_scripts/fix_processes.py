#!/usr/bin/env python3
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(10)

def run_quick(c, cmd, timeout=15):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return str(e)[:100]

# 杀掉所有旧进程
print("=== kill all duplicate processes ===")
run_quick(c, "pkill -9 -f yolo_obstacle_detect.py; echo killed all")

# 清空旧日志
print("=== clear old log ===")
run_quick(c, "> /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log")

# 只启动一个新的
print("=== start single instance ===")
start_cmd = (
    "cd /root/autodl-tmp/streetview_analysis && "
    "nohup python3 yolo_obstacle_detect.py >> yolo_obstacle_run.log 2>&1 & "
    "echo PID=$!"
)
run_quick(c, start_cmd)

# 等待模型加载
import time
time.sleep(30)

# 检查日志（模型加载阶段）
print("\n=== log after 30s ===")
print(run_quick(c, "timeout 10 tail -20 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

# 检查GPU使用
print("\n=== GPU usage ===")
print(run_quick(c, "timeout 10 nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader"))

# 检查进程
print("\n=== process count ===")
print(run_quick(c, "timeout 5 ps aux | grep yolo_obstacle | grep -v grep | wc -l"))

c.close()
