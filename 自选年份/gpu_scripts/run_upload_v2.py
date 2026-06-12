#!/usr/bin/env python3
"""Upload updated seg_inference_offline.py with improved class mapping + overlay + run"""
import paramiko, socket, time, sys
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project/gpu_scripts"
VENV = "/root/venv"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def q(cmd, t=120):
    try:
        ch = c.get_transport().open_session(); ch.settimeout(t)
        ch.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = ch.recv(65536)
                if not chunk: break
                out += chunk
        except socket.timeout: pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERR] {e}"

# Stop old
print("Stopping old process...")
print(q("pkill -f seg_inference; echo OK"))

# Make dir
q(f"mkdir -p {REMOTE}")
q(f"mkdir -p /root/gis_project/outputs/segmentation/viz")

# Upload updated script
sftp = c.open_sftp()
local = Path(__file__).parent / "seg_inference_offline.py"
print(f"Uploading {local.name}...")
sftp.put(str(local), f"{REMOTE}/seg_inference_offline.py")
print(f"  {local.stat().st_size} bytes")
sftp.close()

# Clear checkpoint to re-run all
print("Clearing checkpoint...")
print(q(f"rm -f /root/gis_project/outputs/segmentation/checkpoint.json"))

# Start
print("Starting inference...")
cmd = (
    f"cd /root/gis_project && "
    f"{VENV}/bin/python -u {REMOTE}/seg_inference_offline.py "
    f"> /root/gis_project/logs/seg_inference.log 2>&1 &"
)
chan = c.get_transport().open_session()
chan.settimeout(10)
chan.exec_command(cmd)
try: chan.recv(512)
except socket.timeout: pass
chan.close()
print("  Started!")

# Wait for model load
print("Waiting 60s for model load...")
time.sleep(60)

# Check
print("\n=== GPU ===")
print(q("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader"))
print("\n=== Log tail ===")
print(q("tail -15 /root/gis_project/logs/seg_inference.log"))

c.close()
print("\nDone. Monitoring will continue in background.")
