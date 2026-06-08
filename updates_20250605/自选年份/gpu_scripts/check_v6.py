#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

log_path = "/root/autodl-tmp/seg_inference_v6.log"
try:
    with sftp.open(log_path) as f:
        content = f.read().decode()
        print(f"Log ({len(content)} chars):")
        print(content[-2000:])
except Exception as e:
    print(f"Can't read log: {e}")

# Also check process
stdin, stdout, stderr = client.exec_command("ps aux | grep seg_inference | grep -v grep; echo '---'; ps aux | grep python | grep -v grep | head -5")
out = stdout.read().decode()
print("\nProcesses:", out)

sftp.close()
client.close()
