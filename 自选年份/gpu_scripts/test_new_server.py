#!/usr/bin/env python3
import paramiko, sys

HOST = "connect.bjb1.seetacloud.com"
PORT = 12996
USER = "root"
PW = "roBbKv+ed3Vm"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
    print("CONNECTED!")
    # Quick system check
    stdin, stdout, stderr = client.exec_command("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>&1", timeout=10)
    print("GPU:", stdout.read().decode().strip())
    stdin, stdout, stderr = client.exec_command("df -h /root | tail -1 && ls /root/", timeout=10)
    print("Disk:", stdout.read().decode().strip())
    stdin, stdout, stderr = client.exec_command("which python3 && python3 --version && pip list 2>/dev/null | grep -i -E 'torch|transformers|numpy'", timeout=30)
    print("Python env:", stdout.read().decode().strip())
    stdin, stdout, stderr = client.exec_command("ls /root/gis_project/ 2>&1 || echo 'No gis_project dir'", timeout=10)
    print("gis_project:", stdout.read().decode().strip())
    client.close()
except Exception as e:
    print(f"ERROR: {e}")
