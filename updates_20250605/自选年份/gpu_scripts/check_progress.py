#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

def ssh(cmd):
    s = client.exec_command(cmd, timeout=30)
    return s[1].read().decode().strip()

print("Waiting 20s for processing...")
time.sleep(20)

# Check log
log = ssh("tail -20 /root/autodl-tmp/seg_inference_v6.log")
print("Log:", log[:800])

# Check progress
progress = ssh("wc -l /root/autodl-tmp/outputs/segmentation/seg_results.csv 2>/dev/null")
print("CSV rows:", progress)

viz = ssh("ls /root/autodl-tmp/outputs/segmentation/viz/ 2>/dev/null | wc -l")
print("Viz files:", viz)

# GPU
gpu = ssh("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print("GPU mem:", gpu)

# Process
proc = ssh("ps aux | grep seg_inference | grep -v grep")
print("Process:", proc[:200])

# Sample recent CSV
sample = ssh("tail -3 /root/autodl-tmp/outputs/segmentation/seg_results.csv")
print("Recent CSV:", sample[:400])

client.close()
