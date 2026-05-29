#!/usr/bin/env python3
"""Upload and run the fixed seg_inference script on AutoDL server."""
import paramiko, getpass, sys, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"

# Read password from stdin if available, else use empty
try:
    PW = open(r"e:\xicha gis 智能定位\自选年份\autodl_pwd.txt").read().strip()
except:
    PW = "roBbKv+ed3Vm"

LOCAL_SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_offline_v3.py"
REMOTE_SCRIPT = "/root/gis_project/gpu_scripts/seg_inference_offline_v3.py"
REMOTE_DIR = "/root/gis_project/gpu_scripts"

def ssh_exec(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

print("Connecting to {}@{}:{}...".format(USER, HOST, PORT))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=15)
print("Connected!")

# 1. Kill existing inference processes
print("\n[1/6] Killing existing inference processes...")
out, err = ssh_exec(client, "pkill -f 'seg_inference_offline' ; sleep 1 ; echo 'killed'")
print(out or err)

# 2. Create remote directory
print("\n[2/6] Creating remote directories...")
ssh_exec(client, "mkdir -p /root/gis_project/gpu_scripts")

# 3. Upload script via SFTP
print("\n[3/6] Uploading seg_inference_offline_v3.py...")
sftp = client.open_sftp()
sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
sftp.close()
print("Uploaded!")

# 4. Clear old checkpoint (force re-run with new mappings)
print("\n[4/6] Clearing old checkpoint to force re-run...")
ssh_exec(client, "rm -f /root/gis_project/outputs/segmentation/checkpoint.json")
print("Checkpoint cleared.")

# 5. Find correct python with transformers
print("\n[5/6] Finding Python environment...")
out, _ = ssh_exec(client, "find /root -name 'transformers' -type d 2>/dev/null | head -5")
print("Found transformers in:", out.strip())

# Find python executable
out, _ = ssh_exec(client, r"find /root -name 'python3' -o -name 'python' 2>/dev/null | grep -v '.py' | head -10")
print("Python candidates:", out.strip())

# Try the venv python first
out, err = ssh_exec(client, "source /root/venv/bin/activate && which python && python --version")
print("venv python:", out.strip())

# 6. Find existing running process
out, _ = ssh_exec(client, "ps aux | grep seg_inference")
print("Running processes:", out)

# 7. Start the script in background using nohup
print("\n[6/6] Starting inference with nohup...")
activate = "source /root/venv/bin/activate && "
cmd = "cd /root/gis_project && {} nohup python -u gpu_scripts/seg_inference_offline_v3.py > logs/seg_v3.log 2>&1 &".format(activate)
print("CMD:", cmd)
ssh_exec(client, cmd, timeout=10)

time.sleep(3)

# Check log
out, _ = ssh_exec(client, "tail -30 /root/gis_project/logs/seg_v3.log")
print("\n=== Log tail ===")
print(out)

# Check process
out, _ = ssh_exec(client, "ps aux | grep seg_inference_v3 | grep -v grep")
print("\nRunning process:", out or "Not found")

client.close()
print("\nDone!")
