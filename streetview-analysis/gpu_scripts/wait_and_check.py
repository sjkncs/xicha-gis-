# -*- coding: utf-8 -*-
"""等待N秒后检查推理状态"""
import time, paramiko, socket

time.sleep(120)  # 等待2分钟

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)

def q(cmd, t=8):
    try:
        ch = c.get_transport().open_session()
        ch.settimeout(t)
        ch.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = ch.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout:
            pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except:
        return "[ERR]"

print("=" * 60)
print("  推理状态检查 (2分钟后)")
print("=" * 60)

print("\n[日志]")
print(q('tail -20 /root/gis_project/logs/seg_inference_v2.log'))

print("\n[GPU]")
print(q("nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader"))

print("\n[进程]")
out = q('ps aux | grep seg_inference | grep -v grep')
print(out.strip()[:300] if out.strip() else "NOT RUNNING")

print("\n[已处理]")
print(f"  jpg: {q('ls /root/gis_project/outputs/segmentation/*.png 2>/dev/null | wc -l').strip()}")
print(f"  csv: {q('ls /root/gis_project/outputs/segmentation/*.csv 2>/dev/null | head -3').strip()}")

print("\n[模型]")
print(q("ls /root/gis_project/models/"))

print("\n[全景数据]")
print(f"  jpg: {q('ls /root/gis_project/data/baidu_streetview/*.jpg 2>/dev/null | wc -l').strip()}")
print(f"  JPG: {q('ls /root/gis_project/data/baidu_streetview/*.JPG 2>/dev/null | wc -l').strip()}")

c.close()
print("=" * 60)
