#!/usr/bin/env python3
"""下载 yolov8x-world.pt（Ultralytics World模型，街景友好）"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace").strip(), stdout.channel.recv_exit_status()

# 杀掉残留wget，清理0字节文件
print("=== cleanup ===")
run(c, "pkill -9 wget 2>/dev/null; rm -f /root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-oiv7.pt; echo cleaned")

# 下载 yolov8x-world.pt（Ultralytics官方，无需额外URL）
print("\n=== download yolov8x-world.pt via Python ===")
# 先通过ultralytics下载，它会自动找正确URL
dl_cmd = (
    "cd /root/autodl-tmp/streetview_analysis/yolo_models && "
    "python3 -c \""
    "from ultralytics import YOLO; "
    "m = YOLO('yolov8x-world.pt'); "
    "print('OK, downloaded'); "
    "import os; print(os.path.getsize('/root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-world.pt')//1024//1024, 'MB')\" 2>&1"
)
out, ec = run(c, dl_cmd, timeout=600)
print("EC=%d OUT=%s" % (ec, out[-300:]))

# 确认最终文件
print("\n=== final model files ===")
out, ec = run(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_models/")
print(out)

c.close()
