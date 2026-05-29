#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Test network
print("=== Network test ===")
out, _ = ssh("curl -s --connect-timeout 5 https://huggingface.co 2>&1 | head -3")
print("HF access:", out[:200])

out, _ = ssh("curl -s --connect-timeout 5 https://huggingface.co/api/models/nvidia/segformer-b3-finetuned-ade-512-512 2>&1 | head -5")
print("HF API:", out[:200])

# Check if snapshot_download works
print("\n=== Try snapshot_download ===")
cmd = """python3 -c "
from huggingface_hub import snapshot_download
try:
    path = snapshot_download('nvidia/segformer-b3-finetuned-ade-512-512', cache_dir='/root/autodl-tmp/hf_cache')
    print('SUCCESS:', path)
except Exception as e:
    print('ERROR:', e)
" 2>&1"""
stdin, stdout, stderr = client.exec_command(cmd, timeout=120)
out = stdout.read().decode().strip()
err = stderr.read().decode().strip()
print("stdout:", out[:500])
print("stderr:", err[:300])

client.close()
