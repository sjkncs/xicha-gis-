#!/usr/bin/env python3
import paramiko, sys

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

# Find model dirs
stdin, stdout, stderr = client.exec_command("find /root/autodl-tmp/models -name 'config.json' 2>/dev/null | head -10")
print("Config files:", stdout.read().decode())

# Also check what's in the snapshots dir
stdin, stdout, stderr = client.exec_command("ls -la /root/autodl-tmp/models/transformers_cache/hub/snapshots/default/ 2>/dev/null | head -20")
print("Snapshots:", stdout.read().decode())

# Check what worked before
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/*.py 2>/dev/null | tail -5")
print("Scripts:", stdout.read().decode())

client.close()
