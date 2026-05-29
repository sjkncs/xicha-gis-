#!/usr/bin/env python3
import paramiko, os, sys
sys.stdout.reconfigure(encoding='utf-8')

REMOTE_HOST = "connect.bjb1.seetacloud.com"
REMOTE_PORT = 12996
SSH_USER = "root"
SSH_PASS = "roBbKv+ed3Vm"
BASE = "/root/autodl-tmp/streetview_analysis"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(REMOTE_HOST, port=REMOTE_PORT, username=SSH_USER, password=SSH_PASS)

# Check base directory
stdin, stdout, stderr = ssh.exec_command(f"ls -lh {BASE}/")
print("BASE dir:", stdout.read().decode('utf-8', errors='replace'))

# Check output dir
stdin, stdout, stderr = ssh.exec_command(f"ls -lh {BASE}/output/ 2>/dev/null || echo 'no output dir'")
print("OUTPUT dir:", stdout.read().decode('utf-8', errors='replace'))

# Check heatmaps
stdin, stdout, stderr = ssh.exec_command(f"ls -lh {BASE}/output/heatmaps/ 2>/dev/null || echo 'no heatmaps dir'")
print("HEATMAPS dir:", stdout.read().decode('utf-8', errors='replace'))

# Count pngs in ground_view
stdin, stdout, stderr = ssh.exec_command(f"find {BASE}/output/heatmaps/ -name '*.png' 2>/dev/null | wc -l")
print("Total PNGs:", stdout.read().decode('utf-8', errors='replace').strip())

# Sample of PNG paths (first 5)
stdin, stdout, stderr = ssh.exec_command(f"find {BASE}/output/heatmaps/ -name '*.png' 2>/dev/null | head -5")
print("Sample PNGs:")
for line in stdout.read().decode('utf-8', errors='replace').strip().split('\n'):
    print(f"  {line}")

# Check specific path from earlier grep - use byte search
stdin, stdout, stderr = ssh.exec_command(
    f"find {BASE}/output/heatmaps/yolo_blocked_only/ground_view -type f -name '*.png' 2>/dev/null | head -5"
)
print("\nground_view PNGs:")
out = stdout.read().decode('utf-8', errors='replace').strip()
print(out if out else "(empty)")

ssh.close()
