#!/usr/bin/env python3
"""Download viz output + original for comparison, and check pixel counts."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

local_base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"

# Find original image path
stdin, stdout, stderr = client.exec_command(
    "find /root/autodl-tmp/streetview_analysis/images -name '113.884019_22.500940_E_2022.jpg' 2>/dev/null"
)
orig_path = stdout.read().decode().strip()
print(f"Original path: {orig_path}")

# Download original
if orig_path:
    local_orig = f"{local_base}\\orig_E_113.884019.jpg"
    sftp.get(orig_path, local_orig)
    print(f"Downloaded original image")

# Download viz from outputs
for fn in ["113.884019_22.500940_E_2022_viz.png", "113.884019_22.500940_E_2022_raw.png"]:
    remote = f"/root/autodl-tmp/outputs/segmentation/viz/{fn}"
    local = f"{local_base}\\{fn}"
    try:
        sftp.get(remote, local)
        print(f"Downloaded {fn}")
    except Exception as e:
        print(f"Failed {fn}: {e}")

# Check what the viz output size is
stdin, stdout, stderr = client.exec_command(
    "python3 -c \"from PIL import Image; img=Image.open('/root/autodl-tmp/outputs/segmentation/viz/113.884019_22.500940_E_2022_viz.png'); print(img.size)\""
)
print(f"Viz size: {stdout.read().decode().strip()}")

# Check original size
if orig_path:
    stdin, stdout, stderr = client.exec_command(
        f"python3 -c \"from PIL import Image; img=Image.open('{orig_path}'); print(img.size)\""
    )
    print(f"Original size: {stdout.read().decode().strip()}")

# Count pixel distribution in viz output
stdin, stdout, stderr = client.exec_command(
    "python3 -c \""
    "import numpy as np; from PIL import Image; "
    "img = np.array(Image.open('/root/autodl-tmp/outputs/segmentation/viz/113.884019_22.500940_E_2022_raw.png')); "
    "unique, counts = np.unique(img, return_counts=True); "
    "print('Raw viz unique values:', list(zip(unique.tolist()[:20], counts.tolist()[:20]))\""
)
print(f"Raw viz: {stdout.read().decode().strip()}")

# How many output files exist from v7?
stdin, stdout, stderr = client.exec_command(
    "find /root/autodl-tmp/outputs/segmentation/viz -name '*_viz.png' 2>/dev/null | wc -l"
)
print(f"Total viz files: {stdout.read().decode().strip()}")

sftp.close()
client.close()
