#!/usr/bin/env python3
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    return out, stdout.channel.recv_exit_status()

print("models:")
run(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_models/")
print("processes:")
run(c, "ps aux | grep wget | grep -v grep")
print("images:")
run(c, "find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | wc -l")
c.close()
