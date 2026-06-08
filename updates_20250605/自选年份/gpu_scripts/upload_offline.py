# -*- coding: utf-8 -*-
"""上传离线推理脚本 + 启动"""
import paramiko, socket, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"; PORT = 37625
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"; VENV = "/root/venv"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def q(cmd, t=8):
    try:
        ch = c.get_transport().open_session(); ch.settimeout(t)
        ch.exec_command(cmd); out = b""
        try:
            while True:
                chunk = ch.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout: pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except: return "[ERR]"

sftp = c.open_sftp()
print("=" * 60)
print("  Upload offline script + Start")
print("=" * 60)

# Stop old
print(q("pkill -f seg_inference; echo STOPPED"))

# Upload
local = Path(__file__).parent / "seg_inference_offline.py"
print("Uploading offline script...")
sftp.put(str(local), f"{REMOTE}/gpu_scripts/seg_inference_offline.py")
print(f"  Uploaded: {local.stat().st_size} bytes")

# Clear checkpoint
print(q(f"rm -f {REMOTE}/outputs/segmentation/checkpoint.json; echo CLEANED"))

# Start
print("Starting offline inference...")
cmd = (
    f"mkdir -p {REMOTE}/logs && "
    f"cd {REMOTE} && "
    f"nohup {VENV}/bin/python -u {REMOTE}/gpu_scripts/seg_inference_offline.py "
    f"> {REMOTE}/logs/seg_inference_offline.log 2>&1 &"
)
chan = c.get_transport().open_session()
chan.settimeout(15)
chan.exec_command(cmd)
try: chan.recv(512)
except socket.timeout: pass
chan.close()
print("  Started!")

# Wait 30s
print("\nWaiting 30s for model load...")
time.sleep(30)

# Check
print("\n=== Log ===")
print(q("tail -20 /root/gis_project/logs/seg_inference_offline.log"))
print("\n=== GPU ===")
print(q("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader"))
print("\n=== Process ===")
out = q("ps aux | grep seg_inference | grep -v grep")
print(out.strip()[:200] if out.strip() else "NOT RUNNING")

sftp.close()
c.close()
print("=" * 60)
