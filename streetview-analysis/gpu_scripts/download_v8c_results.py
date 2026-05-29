#!/usr/bin/env python3
"""Download v8c results and sample viz outputs."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()

local_base = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"

# Download CSVs
for csv_name in ["per_image_metrics.csv", "per_location_metrics.csv", "summary.txt"]:
    remote = f"/root/autodl-tmp/outputs/v8c/{csv_name}"
    local = f"{local_base}\\{csv_name}"
    try:
        sftp.get(remote, local)
        print(f"Downloaded {csv_name}")
    except Exception as e:
        print(f"Failed {csv_name}: {e}")

# Download 2 sample viz outputs
viz_dir = "/root/autodl-tmp/outputs/v8c/viz"
stdin, stdout, stderr = client.exec_command(f"ls {viz_dir}/*.png 2>/dev/null | head -4")
viz_files = stdout.read().decode().strip().split("\n")
print(f"Found {len(viz_files)} viz files")
for vf in viz_files[:4]:
    vf = vf.strip()
    if not vf:
        continue
    fname = vf.split("/")[-1]
    local = f"{local_base}\\v8c_{fname}"
    try:
        sftp.get(vf, local)
        print(f"Downloaded {fname}")
    except Exception as e:
        print(f"Failed {fname}: {e}")

# Also download the original images corresponding to those viz
# Read first few lines of per-location CSV
print("\n--- Per-location CSV head ---")
with open(f"{local_base}\\per_location_metrics.csv", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i < 5:
            print(line.strip())
        else:
            break

# Print summary
print("\n--- Summary ---")
with open(f"{local_base}\\summary.txt", encoding="utf-8") as f:
    print(f.read())

sftp.close()
client.close()
