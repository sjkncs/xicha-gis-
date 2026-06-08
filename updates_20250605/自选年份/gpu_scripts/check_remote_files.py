#!/usr/bin/env python3
import paramiko, os, sys

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER   = "root"
SSH_PASS   = "roBbKv+ed3Vm"
REMOTE_BASE = "/root/autodl-tmp/streetview_analysis"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)
stdin, stdout, stderr = ssh.exec_command(f"find {REMOTE_BASE} -name '*.png' -o -name '*.jpg' -o -name '*.json' -o -name '*.log' 2>/dev/null | grep -v images | grep -v yolo_models | sort")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("Files on remote:")
print(out if out else "(none)")
if err:
    print("Errors:", err)

# Also check sizes
stdin, stdout, stderr = ssh.exec_command(f"find {REMOTE_BASE} -maxdepth 1 \\( -name '*.png' -o -name '*.jpg' -o -name '*.json' -o -name '*.log' \\) -exec ls -lh {{}} \\; 2>/dev/null")
out = stdout.read().decode('utf-8', errors='replace')
print("\nFile sizes in base dir:")
print(out if out else "(none)")

ssh.close()
