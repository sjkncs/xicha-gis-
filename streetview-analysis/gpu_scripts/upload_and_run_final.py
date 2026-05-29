#!/usr/bin/env python3
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(30)
sftp = c.open_sftp()

def r(c, cmd, timeout=30):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return "ERR:" + str(e)[:200]

# 杀掉所有旧进程
print("killing old processes...")
r(c, "kill -9 $(ps aux | grep 'final_obstacle\|yolo_obstacle\|diag' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")

# 上传脚本
print("uploading final_obstacle_detect.py...")
script_content = open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\final_obstacle_detect.py", "r", encoding="utf-8").read()
sftp.file(f"{REMOTE_DIR}/final_obstacle_detect.py", "wb").write(script_content.encode("utf-8"))
print("uploaded")

# 清空旧日志
r(c, "> /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log")

# 启动
print("starting...")
start = (
    f"cd {REMOTE_DIR} && "
    "python3 -u final_obstacle_detect.py >> yolo_obstacle_run.log 2>&1 & "
    "echo PID=$!"
)
r(c, start)
sftp.close()

# 等待60秒后检查状态
print("Waiting 60s for startup...")
time.sleep(60)

# 检查
c2 = paramiko.SSHClient()
c2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c2.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c2.get_transport().set_keepalive(10)

def r2(c, cmd, timeout=30):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except:
        return "ERR"

print("\n=== log after 60s ===")
print(r2(c2, "tail -20 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== GPU ===")
print(r2(c2, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process ===")
print(r2(c2, "ps aux | grep final_obstacle | grep -v grep"))

print("\n=== processed images ===")
print(r2(c2, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' 2>/dev/null | wc -l"))

c2.close()
print("\ndone")
