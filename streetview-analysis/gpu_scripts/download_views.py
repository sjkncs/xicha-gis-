#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

client.exec_command("ps aux | grep seg_inference | grep -v grep | awk '{print $2}' | xargs -r kill -9")

# Upload save_views
with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\save_views.py") as f:
    content = f.read()
with sftp.open("/root/autodl-tmp/save_views.py", "w") as f:
    f.write(content)
print("Uploaded save_views.py")

# Run it
stdin, stdout, stderr = client.exec_command("cd /root/autodl-tmp && python3 save_views.py 2>&1", timeout=60)
print(stdout.read().decode())
if stderr.read(): pass

# Download the saved views
for name in ["original", "F", "R", "B", "L"]:
    remote = f"/root/autodl-tmp/view_{name}.png"
    local = f"e:\\xicha gis 智能定位\\自选年份\\gpu_scripts\\view_{name}.png"
    try:
        sftp.get(remote, local)
        print(f"Downloaded view_{name}.png")
    except:
        print(f"Failed to download view_{name}.png")

sftp.close()
client.close()
