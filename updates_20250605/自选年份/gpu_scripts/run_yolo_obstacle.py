#!/usr/bin/env python3
import paramiko, os, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace").strip()

# 杀掉残留进程
print("killing old processes...")
run(c, "pkill -9 -f yolo_obstacle 2>/dev/null; pkill -9 wget 2>/dev/null; echo killed")

# 上传脚本
print("uploading script...")
sftp.put(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\yolo_obstacle_detect.py",
         f"{REMOTE_DIR}/yolo_obstacle_detect.py")
print("uploaded")

# 启动后台运行
print("starting detection...")
run_cmd = (
    f"cd {REMOTE_DIR} && "
    "nohup python3 yolo_obstacle_detect.py > yolo_obstacle_run.log 2>&1 & "
    "echo PID=$! && sleep 3 && head -5 yolo_obstacle_run.log"
)
out = run(c, run_cmd)
print("START OUTPUT:", out)

c.close()
