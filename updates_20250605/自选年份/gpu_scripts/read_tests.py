#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

for fname in ["test_server_model.py", "test_full_pipeline.py"]:
    print(f"\n===== {fname} =====")
    try:
        with sftp.open(f"/root/autodl-tmp/{fname}") as f:
            content = f.read().decode("utf-8", errors="replace")
            # Print first 50 lines
            lines = content.split("\n")[:60]
            for i, line in enumerate(lines):
                print(f"{i+1:3d}| {line}")
    except Exception as e:
        print(f"Error: {e}")

sftp.close()
client.close()
