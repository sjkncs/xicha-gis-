#!/usr/bin/env python3
"""Download v7 viz outputs and compare with original images."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

local_base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"

# Check how many viz files exist
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/outputs/segmentation/viz/*.png 2>/dev/null | wc -l")
count = int(stdout.read().strip())
print(f"Viz files: {count}")

# List first 10
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/outputs/segmentation/viz/*.png 2>/dev/null | head -10")
print(stdout.read().decode())

# Download first 2 viz outputs
for i, line in enumerate(stdout.read().decode().strip().split("\n")[:2]):
    line = line.strip()
    if not line:
        continue
    remote = line
    fname = remote.split("/")[-1]
    local = f"{local_base}\\{fname}"
    try:
        sftp.get(remote, local)
        print(f"Downloaded {fname}")
    except Exception as e:
        print(f"Failed {fname}: {e}")

# Check original images in subdirs
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/streetview_analysis/images/ 2>/dev/null | head -10")
print("\nImage subdirs:", stdout.read().decode())

# Count total images
stdin, stdout, stderr = client.exec_command("find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | wc -l")
print("Total images:", stdout.read().decode())

sftp.close()
client.close()
