#!/usr/bin/env python3
import paramiko, sys

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip(): print(f"ERR: {err.strip()[:100]}")
    return out

print("=== /root/autodl-tmp/ ===")
print(run("ls -la /root/autodl-tmp/"))

print("\n=== samples/ ===")
print(run("ls -la /root/autodl-tmp/streetview_sim/samples/"))

print("\n=== 全部图片 ===")
out = run('find /root/autodl-tmp/ -type f -name "*.jpg" 2>/dev/null | head -30')
print(f"JPG files:\n{out}")
out = run('find /root/autodl-tmp/ -type f -name "*.png" 2>/dev/null | head -10')
print(f"PNG files:\n{out}")

print("\n=== 全部JSON ===")
print(run('find /root/autodl-tmp/ -name "*.json" -type f 2>/dev/null'))

# 也搜索旧IP的数据
print("\n=== 搜索其他可能的数据目录 ===")
print(run('find / -maxdepth 4 -name "sim_results*" -type f 2>/dev/null | head -20'))
print(run('find / -maxdepth 4 -name "*streetview*" -type d 2>/dev/null | head -10'))
print(run('find / -maxdepth 4 -name "results" -type d 2>/dev/null | head -10'))

ssh.close()
print("\nDone")
