#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

# Find actual image directory
stdin, stdout, stderr = client.exec_command("find /root/autodl-tmp -name '*.jpg' 2>/dev/null | head -5")
print("JPG files:", stdout.read().decode())
stdin, stdout, stderr = client.exec_command("find /root/autodl-tmp -name '*.png' 2>/dev/null | head -5")
print("PNG files:", stdout.read().decode())
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/ 2>/dev/null")
print("Root dirs:", stdout.read().decode())

client.close()
