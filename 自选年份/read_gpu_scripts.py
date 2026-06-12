#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()

files = [
    "/root/gis_project/gpu_scripts/setup_step1_env.sh",
    "/root/gis_project/gpu_scripts/setup_full.sh",
]

for f in files:
    print(f"\n{'='*60}")
    print(f"# {f}")
    print('='*60)
    out = run(c, f"cat {f}")
    print(out)

c.close()
