#!/usr/bin/env python3
"""Check old v7 results and download a viz for comparison."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

local_base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"

# Check old segmentation results
stdin, stdout, stderr = client.exec_command("ls /root/autodl-tmp/streetview_analysis/segmentation_results_v3/ 2>/dev/null | head -10")
print("Old results:", stdout.read().decode())

# Check v7 log
stdin, stdout, stderr = client.exec_command("tail -50 /root/autodl-tmp/seg_inference_v7.log 2>/dev/null")
print("\nV7 log tail:", stdout.read().decode())

# Check the v8b results we just computed
stdin, stdout, stderr = client.exec_command("tail -10 /root/autodl-tmp/v8b_results.txt 2>/dev/null")
print("\nV8b results:", stdout.read().decode())

# Download one viz output
for remote_name in ["113.884019_22.500940_E_2022_viz.png", "113.884019_22.500940_E_2022.png"]:
    remote = f"/root/autodl-tmp/outputs/segmentation/viz/{remote_name}"
    local = f"{local_base}\\{remote_name}"
    try:
        sftp.get(remote, local)
        print(f"Downloaded {remote_name}")
    except Exception as e:
        print(f"Failed {remote_name}: {e}")

# Download original image
orig = "/root/autodl-tmp/streetview_analysis/images/景区/113.884019_22.500940/113.884019_22.500940_E_2022.jpg"
local_orig = f"{local_base}\\orig_113.884019_22.500940_E_2022.jpg"
try:
    sftp.get(orig, local_orig)
    print(f"Downloaded original")
except Exception as e:
    print(f"Failed original: {e}")

sftp.close()
client.close()
