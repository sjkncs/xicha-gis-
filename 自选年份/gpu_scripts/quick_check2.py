#!/usr/bin/env python3
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
print("connected OK")

stdin, stdout, stderr = c.exec_command("ls /root/autodl-tmp/streetview_analysis/yolo_models/", timeout=30)
print("models:", stdout.read().decode())
stdin2, stdout2, stderr2 = c.exec_command("find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | wc -l", timeout=30)
print("images:", stdout2.read().decode())
stdin3, stdout3, stderr3 = c.exec_command("ps aux | grep wget | grep -v grep | wc -l", timeout=30)
print("wget procs:", stdout3.read().decode())
stdin4, stdout4, stderr4 = c.exec_command("ls -lh /root/autodl-tmp/streetview_analysis/yolo_models/", timeout=30)
print("model files:", stdout4.read().decode())
c.close()
