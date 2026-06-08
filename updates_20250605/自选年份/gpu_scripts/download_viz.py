#!/usr/bin/env python3
"""Download original and projected images from server."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

# List first few images
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/streetview_analysis/images/*.jpg 2>/dev/null | head -5")
print("First images:", stdout.read().decode().strip())

# Get first image size info
stdin, stdout, stderr = client.exec_command("python3 -c \"from PIL import Image; img=Image.open('/root/autodl-tmp/streetview_analysis/images/113.9263685_22.5129279_E_2022.jpg'); print(img.size, img.mode)\"")
print("E image:", stdout.read().decode().strip())

# Download all views
local_base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"
for name in ["original", "F", "R", "B", "L"]:
    remote = f"/root/autodl-tmp/view_{name}.png"
    local = f"{local_base}\\view_{name}.png"
    try:
        sftp.get(remote, local)
        from PIL import Image
        img = Image.open(local)
        print(f"Downloaded view_{name}.png: {img.size}")
    except Exception as e:
        print(f"view_{name}.png: {e}")

# Also try to get a viz output from v7
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/outputs/segmentation/viz/*.png 2>/dev/null | head -3")
print("Viz files:", stdout.read().decode().strip())

sftp.close()
client.close()
