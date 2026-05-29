#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

print("=== Log tail ===")
out, _ = ssh("tail -30 /root/gis_project/logs/seg_v5.log")
print(out[:1000])

print("\n=== CSV sample ===")
out, _ = ssh("cat /root/autodl-tmp/outputs/segmentation/seg_results.csv")
print(out[:1500])

print("\n=== Viz files ===")
out, _ = ssh("ls /root/autodl-tmp/outputs/segmentation/viz/ 2>/dev/null | head -10")
print(out[:300])

print("\n=== GPU mem ===")
out, _ = ssh("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print("Mem:", out.strip(), "MiB")

print("\n=== Config.json content ===")
out, _ = ssh("cat /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json")
print(out[:500])

client.close()
