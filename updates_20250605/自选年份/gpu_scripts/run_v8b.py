#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v8b.py", encoding="utf-8") as f:
    content = f.read()
with sftp.open("/root/autodl-tmp/seg_inference_v8b.py", "w") as f:
    f.write(content)
print("Uploaded v8b")

stdin, stdout, stderr = client.exec_command(
    "cd /root/autodl-tmp && python3 seg_inference_v8b.py 2>&1",
    timeout=600
)
stdout.channel.recv_exit_status()
print(stdout.read().decode())
if stderr.read():
    pass

sftp.close()
client.close()
