# -*- coding: utf-8 -*-
import time, paramiko, socket
time.sleep(60)

HOST = "connect.bjb1.seetacloud.com"; PORT = 37625; USER = "root"; PASS = "roBbKv+ed3Vm"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def q(cmd, t=8):
    try:
        ch = c.get_transport().open_session(); ch.settimeout(t)
        ch.exec_command(cmd); out = b""
        try:
            while True:
                chunk = ch.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout: pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except: return "[ERR]"

print("=" * 60)
print("  推理状态 (1分钟后)")
print("=" * 60)
print("\n[日志]")
print(q("tail -20 /root/gis_project/logs/seg_inference_v2.log"))
print("\n[GPU]")
print(q("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader"))
print("\n[进程]")
out = q("ps aux | grep seg_inference | grep -v grep")
print(out.strip()[:300] if out.strip() else "NOT RUNNING")
print("\n[结果]")
print("viz:", q("ls /root/gis_project/outputs/segmentation/*.png 2>/dev/null | wc -l"))
print("csv:", q("ls /root/gis_project/outputs/segmentation/*.csv 2>/dev/null"))
c.close()
print("=" * 60)
