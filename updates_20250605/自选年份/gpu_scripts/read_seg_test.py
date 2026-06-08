#!/usr/bin/env python3
# Read seg_test.py from server to see how it loaded model
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

with sftp.open("/root/autodl-tmp/seg_test.py") as f:
    print(f.read().decode())

sftp.close()
client.close()
