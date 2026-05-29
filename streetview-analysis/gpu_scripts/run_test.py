#!/usr/bin/env python3
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(10)

def r(c, cmd, timeout=30):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return "ERR:" + str(e)[:100]

# 杀掉所有旧进程
r(c, "pkill -9 -f yolo_obstacle 2>/dev/null; echo killed")
time.sleep(2)

# 上传测试脚本
sftp = c.open_sftp()
sftp.put(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\test_yolo11x.py",
         f"{REMOTE_DIR}/test_yolo11x.py")
sftp.close()
print("uploaded")

# 启动测试
r(c, "cd /root/autodl-tmp/streetview_analysis && python3 -u test_yolo11x.py > test_yolo11x.log 2>&1 & echo started")

# 等待30秒（模型加载）
time.sleep(30)

print("\n=== log ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/test_yolo11x.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process ===")
print(r(c, "ps aux | grep test_yolo | grep -v grep"))

c.close()
