#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

def ssh(cmd):
    s = client.exec_command(cmd, timeout=30)
    return s[1].read().decode().strip()

print("Waiting 60s for more processing...")
time.sleep(60)

rows = ssh("wc -l /root/autodl-tmp/outputs/segmentation/seg_results.csv")
viz = ssh("ls /root/autodl-tmp/outputs/segmentation/viz/ | wc -l")
gpu = ssh("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
proc = ssh("ps aux | grep seg_inference | grep -v grep")
print(f"CSV rows: {rows}")
print(f"Viz files: {viz}")
print(f"GPU mem: {gpu}")
print(f"Process: {proc[:200]}")
print(f"\nRecent CSV rows:")
for line in ssh("tail -10 /root/autodl-tmp/outputs/segmentation/seg_results.csv").split('\n'):
    print(f"  {line[:200]}")

client.close()
