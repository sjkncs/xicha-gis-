#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\test_full_pipeline.py"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()
sftp.put(SCRIPT, "/root/autodl-tmp/test_full_pipeline.py")

client.exec_command("ps aux | grep seg_inference | grep -v grep | awk '{print $2}' | xargs -r kill -9")

stdin, stdout, stderr = client.exec_command("cd /root/autodl-tmp && python3 test_full_pipeline.py 2>&1", timeout=180)
out = stdout.read().decode()
err = stderr.read().decode()
print("OUT:", out[:4000])
if err: print("ERR:", err[:500])

sftp.close()
client.close()
