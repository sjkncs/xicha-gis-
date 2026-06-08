#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

try:
    with sftp.open("/root/autodl-tmp/seg_inference_v6.log") as f:
        print(f.read().decode())
except Exception as e:
    print(f"Can't read: {e}")

# Kill process
client.exec_command("ps aux | grep seg_inference | grep -v grep | awk '{print $2}' | xargs -r kill -9")
print("\nProcess killed.")

# Check latest CSV line
stdin, stdout, stderr = client.exec_command("tail -1 /root/autodl-tmp/outputs/segmentation/seg_results.csv")
print("Last CSV:", stdout.read().decode().strip())

sftp.close()
client.close()
