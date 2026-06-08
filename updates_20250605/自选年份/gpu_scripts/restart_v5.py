#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v5.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()
print("Uploading...")
sftp.put(SCRIPT_LOCAL, "/root/gis_project/seg_inference_v5.py")
sftp.close()
print("Uploaded!")

ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

ssh("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
ssh("pkill -f seg_inference 2>/dev/null; sleep 1")
print("Cleared checkpoint, killed old processes")

# Count images first
out, _ = ssh("find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' | wc -l")
print("Total images:", out)

# Start
print("Starting inference...")
client.exec_command("cd /root/gis_project && python3 -u seg_inference_v5.py > logs/seg_v5.log 2>&1 &", timeout=10)
time.sleep(20)

print("\n=== Status ===")
out, _ = ssh("tail -15 /root/gis_project/logs/seg_v5.log")
print("Log:", out[:600])

out, _ = ssh("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print("GPU mem:", out.strip(), "MiB")

out, _ = ssh("ps aux | grep seg_inference | grep -v grep")
print("Process:", out[:200] or "NOT RUNNING")

out, _ = ssh("wc -l /root/autodl-tmp/outputs/segmentation/seg_results.csv 2>/dev/null")
print("CSV rows:", out)

client.close()
print("\nDone!")
