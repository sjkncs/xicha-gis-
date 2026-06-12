#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

# Try running the script directly with timeout to capture error
cmd = "cd /root/autodl-tmp && python3 seg_inference_v6.py 2>&1 | head -30; echo EXIT=$?"
stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
out = stdout.read().decode()
err = stderr.read().decode()
print("STDOUT:", out[:2000])
print("STDERR:", err[:1000])

# Also check nohup.out
stdin, stdout, stderr = client.exec_command("cat /root/nohup.out 2>/dev/null | tail -20; echo '---'; ls -la /root/*.out 2>/dev/null")
out2 = stdout.read().decode()
print("\nnohup.out:", out2[:1000])

client.close()
