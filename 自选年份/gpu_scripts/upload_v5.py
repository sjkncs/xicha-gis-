#!/usr/bin/env python3
"""Upload v5 script and start inference."""
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v5.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

# Upload
print("Uploading v5 script...")
sftp.put(SCRIPT_LOCAL, "/root/gis_project/seg_inference_v5.py")
sftp.close()
print("Uploaded!")

ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Clear old
print("Clearing checkpoint...")
ssh("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
print("Checkpoint cleared")

# Kill old
print("Killing old processes...")
ssh("pkill -f seg_inference 2>/dev/null; sleep 1; echo done")

# Verify model files
out, _ = ssh("ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/")
print("\nModel files:", out[:300])

# Start v5
print("\nStarting v5 inference...")
client.exec_command("cd /root/gis_project && python3 -u seg_inference_v5.py > logs/seg_v5.log 2>&1 &", timeout=10)
print("Inference started!")
time.sleep(20)

# Check
print("\n=== Status Check ===")
out, _ = ssh("tail -30 /root/gis_project/logs/seg_v5.log")
print("Log:", out[:600])

out, _ = ssh("nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader")
print("GPU mem:", out.strip())

out, _ = ssh("ps aux | grep seg_inference | grep -v grep")
print("Process:", out[:200] or "NOT RUNNING")

out, _ = ssh("ls /root/autodl-tmp/outputs/segmentation/*.csv 2>/dev/null | head -5")
print("CSV files:", out[:200])

client.close()
print("\nDone!")
