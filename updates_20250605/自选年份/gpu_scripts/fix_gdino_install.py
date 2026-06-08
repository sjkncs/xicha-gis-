#!/usr/bin/env python3
import paramiko, subprocess

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

# 检查仓库结构
stdin, stdout, stderr = c.exec_command("find /root/autodl-tmp/streetview_analysis/groundingdino_repo -name '*.py' 2>/dev/null | head -30", timeout=30)
print("=== repo .py files ===")
print(stdout.read().decode("utf-8", errors="replace"))

# 检查config目录
stdin2, stdout2, stderr2 = c.exec_command("ls /root/autodl-tmp/streetview_analysis/groundingdino_repo/", timeout=30)
print("=== repo root ===")
print(stdout2.read().decode("utf-8", errors="replace"))

# 找config.py
stdin3, stdout3, stderr3 = c.exec_command("find /root/autodl-tmp/streetview_analysis/groundingdino_repo -name 'config.py' 2>/dev/null", timeout=30)
print("=== config.py locations ===")
print(stdout3.read().decode("utf-8", errors="replace"))

# 手动安装，不走editable模式
print("\n=== 安装 groundingdino (非editable) ===")
cmd = "cd /root/autodl-tmp/streetview_analysis/groundingdino_repo && pip install -q . 2>&1 | tail -10"
stdin4, stdout4, stderr4 = c.exec_command(cmd, timeout=300)
print(stdout4.read().decode("utf-8", errors="replace"))
print(stderr4.read().decode("utf-8", errors="replace")[-300:])

c.close()
