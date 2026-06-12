#!/usr/bin/env python3
"""Fix model dir structure AND restart inference."""
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()
sftp = client.open_sftp()

# Read current v4 script
with sftp.file("/root/gis_project/seg_inference_v4.py", "r") as f:
    script = f.read().decode()

# Show key lines
print("Current script MODEL lines:")
for line in script.split('\n'):
    if any(k in line for k in ['MODEL_DIR', 'MODEL_LOCAL', 'snapshots', 'from_pretrained']):
        print(f"  {line.strip()[:100]}")

# Find actual file locations on server
out, _ = ssh("find /root/autodl-tmp/models -maxdepth 5 -type f 2>/dev/null | head -10")
print("\nActual files:", out[:300])

out, _ = ssh("find /root/autodl-tmp/models -maxdepth 5 -type d 2>/dev/null | head -10")
print("Dirs:", out[:300])

# Reorganize: move snapshots -> hub/...
print("\nReorganizing...")
# Create hub structure
ssh("mkdir -p /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots")
# Move
out, err = ssh("mv /root/autodl-tmp/models/snapshots/default /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default && echo OK")
print("Move:", out, err[:100] if err else "")

# Verify
out, _ = ssh("find /root/autodl-tmp/models/hub -type f | head -10")
print("After move:", out[:400])

out, _ = ssh("ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/")
print("Snapshot:", out[:400])

# Now fix the script: MODEL_DIR should point to the hub dir so from_pretrained can resolve it
# Replace MODEL_DIR in the script
script = script.replace(
    'MODEL_DIR = Path("/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512")',
    'MODEL_DIR = Path("/root/autodl-tmp/models")'
)
script = script.replace(
    'MODEL_LOCAL = MODEL_DIR / "snapshots/default"',
    'MODEL_LOCAL = Path("/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default")'
)
# from_pretrained should use MODEL_LOCAL (the actual path)
script = script.replace(
    'SegformerImageProcessor.from_pretrained(\n        str(MODEL_DIR), local_files_only=True)',
    'SegformerImageProcessor.from_pretrained(\n        str(MODEL_LOCAL), local_files_only=True)'
)
# Also fix model loading
script = script.replace(
    'SegformerForSemanticSegmentation.from_pretrained(\n        str(MODEL_DIR), local_files_only=True)',
    'SegformerForSemanticSegmentation.from_pretrained(\n        str(MODEL_LOCAL), local_files_only=True)'
)
# Also fix the log line
script = script.replace(
    'log("Loading model from: {}".format(MODEL_LOCAL))',
    'log("Loading model from: {}".format(MODEL_LOCAL))'
)

# Write fixed script
sftp.file("/root/gis_project/seg_inference_v4.py", "w").write(script.encode())
sftp.close()
print("\nScript updated!")

# Verify script fix
client2 = paramiko.SSHClient()
client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client2.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh2 = lambda cmd, t=30: (lambda s=client2.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

print("\nUpdated script key lines:")
for line in script.split('\n'):
    if any(k in line for k in ['MODEL_DIR', 'MODEL_LOCAL', 'from_pretrained', 'snapshots']):
        print(f"  {line.strip()[:100]}")

# Clear and restart
print("\n=== Restart ===")
ssh2("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
ssh2("pkill -f seg_inference 2>/dev/null; sleep 1")
client2.exec_command("cd /root/gis_project && python3 -u seg_inference_v4.py > logs/seg_v4.log 2>&1 &", timeout=10)
print("Inference started!")
time.sleep(15)

out, _ = ssh2("tail -30 /root/gis_project/logs/seg_v4.log")
print("\nLog:", out[:600])

out, _ = ssh2("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print("GPU mem:", out.strip())

out, _ = ssh2("ps aux | grep seg_inference | grep -v grep")
print("Process:", out[:200] or "NOT RUNNING")

client2.close()
print("\nDone!")
