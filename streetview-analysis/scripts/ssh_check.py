#!/usr/bin/env python3
import paramiko
import sys

host = "connect.bjb1.seetacloud.com"
port = 37625
username = "root"
password = "roBbKv+ed3Vm"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=username, password=password, timeout=30)

# 检查GPU
stdin, stdout, stderr = client.exec_command("nvidia-smi 2>/dev/null || echo 'NO_NVIDIA_SMI'; echo '---'; python3 --version 2>/dev/null || python --version 2>/dev/null; echo '---'; df -h / | tail -1; echo '---'; free -h; echo '---'; ls /root/ 2>/dev/null || echo 'no /root'; echo '---DONE---'")
output = stdout.read().decode('utf-8', errors='replace')
print(output)
client.close()
