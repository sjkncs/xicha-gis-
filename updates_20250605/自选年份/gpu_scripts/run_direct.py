#!/usr/bin/env python3
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

# Run script directly (not background) to capture errors
cmd = "cd /root/gis_project && python3 -u seg_inference_v5.py 2>&1 | head -50"
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print("STDOUT:")
print(out[:1000])
print("STDERR:")
print(err[:500])

client.close()
