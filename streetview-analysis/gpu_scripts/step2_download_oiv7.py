#!/usr/bin/env python3
"""下载 yolov8x-oiv7.pt + 确认图片路径"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(c, cmd, timeout=600):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    exit_code = stdout.channel.recv_exit_status()
    return out, exit_code

# 下载 yolov8x-oiv7
print("=== downloading yolov8x-oiv7.pt ===")
out, ec = run(c,
    "mkdir -p /root/autodl-tmp/streetview_analysis/yolo_models && "
    "cd /root/autodl-tmp/streetview_analysis/yolo_models && "
    "wget -q --show-progress -O yolov8x-oiv7.pt "
    "'https://github.com/ultralytics/ultralytics/releases/download/v8.3.0/yolov8x-oiv7.pt' 2>&1 | tail -5",
    timeout=600)
print("EC=%d OUT=%s" % (ec, out[-200:]))

out2, ec2 = run(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_models/")
print("models now: %s" % out2)

# 确认图片路径
print("\n=== 确认图片 ===")
out, ec = run(c, "find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | wc -l")
print("jpg count: %s" % out)
out, ec = run(c, "find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | head -3")
print("samples: %s" % out)

c.close()
print("done")
