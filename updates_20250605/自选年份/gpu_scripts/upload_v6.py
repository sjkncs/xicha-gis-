#!/usr/bin/env python3
"""Upload v6 and restart inference."""
import paramiko, time, os, sys

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v6.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

# Kill old processes
stdin, stdout, stderr = client.exec_command("ps aux | grep seg_inference | grep -v grep | awk '{print $2}' | xargs -r kill -9; echo done")
print("Kill:", stdout.read().decode().strip())

# Upload script
remote_path = "/root/autodl-tmp/seg_inference_v6.py"
print(f"Uploading {os.path.basename(SCRIPT)}...")
sftp.put(SCRIPT, remote_path)
print("Upload done.")

# Clear old checkpoint to re-process remaining images
stdin, stdout, stderr = client.exec_command(
    "rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json && "
    "rm -f /root/autodl-tmp/outputs/segmentation/inference.log && "
    "echo checkpoint cleared"
)
print("Clear checkpoint:", stdout.read().decode().strip())

# Start inference
print("Starting v6 inference...")
stdin, stdout, stderr = client.exec_command(
    f"cd /root/autodl-tmp && nohup python3 {remote_path} > {remote_path}.log 2>&1 & echo pid=$!"
)
out = stdout.read().decode().strip()
print("Start output:", out)
time.sleep(3)

# Quick check
stdin, stdout, stderr = client.exec_command("head -5 /root/autodl-tmp/seg_inference_v6.log 2>/dev/null; echo '---'; ps aux | grep seg_inference | grep -v grep | head -2")
out = stdout.read().decode().strip()
print("Status:\n", out)

sftp.close()
client.close()
print("Done.")
