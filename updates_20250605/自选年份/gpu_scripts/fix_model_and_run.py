#!/usr/bin/env python3
"""Extract model zip at correct path and restart inference."""
import paramiko, time

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
LOCAL_ZIP = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_segformer_b3.zip"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()
sftp = client.open_sftp()

print("Step 1: Upload model zip to correct location...")
zip_sz = 0
import os
if os.path.exists(LOCAL_ZIP):
    zip_sz = os.path.getsize(LOCAL_ZIP) / 1024 / 1024
    print(f"Zip size: {zip_sz:.1f}MB")

    def progress(c, t):
        if t > 0:
            print(f"\r  {c/1024/1024:.1f}/{t/1024/1024:.1f}MB ({c/t*100:.0f}%)", end="", flush=True)
    t0 = time.time()
    # Upload directly to /root/autodl-tmp/models/ 
    REMOTE_ZIP = "/root/autodl-tmp/models/segformer_b3.zip"
    sftp.put(LOCAL_ZIP, REMOTE_ZIP, callback=progress)
    print(f"\nUploaded in {time.time()-t0:.1f}s")
else:
    print(f"Zip not found at {LOCAL_ZIP}")
    client.close()
    exit(1)
sftp.close()

print("\nStep 2: Extract at correct location...")
# The zip contains: hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/*
# We want these files at: /root/autodl-tmp/models/hub/...
# So extract directly into /root/autodl-tmp/models/
out, err = ssh("cd /root/autodl-tmp/models && rm -rf hub && unzip -o segformer_b3.zip && rm segformer_b3.zip && echo 'OK'")
print("Extract:", out[:200])
if err:
    print("ERR:", err[:200])

print("\nStep 3: Verify model files...")
out, _ = ssh("find /root/autodl-tmp/models -type f | head -10")
print("Files:", out[:400])

out, _ = ssh("ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/ 2>/dev/null || echo 'NOT FOUND'")
print("Snapshot:", out[:400])

# Check key files
for fname in ["config.json", "preprocessor_config.json", "pytorch_model.bin"]:
    out, _ = ssh(f"ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/{fname} 2>&1")
    print(f"  {fname}: {out[:100]}")

print("\nStep 4: Upload and run fixed inference script...")
# The current seg_inference_v3_server2.py loads from MODEL_DIR = /root/autodl-tmp/models
# and uses MODEL_DIR as repo_id. Let's verify it will work.
# The MODEL_DIR is /root/autodl-tmp/models and the model is at:
# /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default
# The from_pretrained(repo_id=MODEL_DIR) will try to load from MODEL_DIR
# This works IF MODEL_DIR/name/snapshots/default has the files
# But MODEL_DIR = /root/autodl-tmp/models and the actual files are at
# /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default

# Fix: update script to use the correct path as MODEL_DIR
SCRIPT_LOCAL = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v3_server2.py"
with open(SCRIPT_LOCAL, "r", encoding="utf-8") as f:
    content = f.read()

# Update MODEL_DIR to point to the hub cache dir
content = content.replace(
    'MODEL_DIR = Path("/root/autodl-tmp/models")',
    'MODEL_DIR = Path("/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512")'
)

# Also update MODEL_LOCAL to be the snapshots/default inside MODEL_DIR
content = content.replace(
    'MODEL_LOCAL = MODEL_DIR / "hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"',
    'MODEL_LOCAL = MODEL_DIR / "snapshots/default"'
)

SCRIPT_V4 = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v4.py"
with open(SCRIPT_V4, "w", encoding="utf-8") as f:
    f.write(content)
print("Script v4 written")

# Upload
sftp = client.open_sftp()
sftp.put(SCRIPT_V4, "/root/gis_project/seg_inference_v4.py")
sftp.close()
print("Uploaded v4 script")

# Clear checkpoint
ssh("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")

# Kill old processes
ssh("pkill -f seg_inference 2>/dev/null; sleep 1")

# Start
start = "cd /root/gis_project && python3 -u seg_inference_v4.py > logs/seg_v4.log 2>&1 &"
client.exec_command(start, timeout=10)
print("Inference v4 started!")
time.sleep(10)

# Check
print("\nStep 5: Check status...")
out, _ = ssh("tail -30 /root/gis_project/logs/seg_v4.log")
print("Log:", out[:500])

out, _ = ssh("nvidia-smi --query-gpu=memory.used --format=csv,noheader")
print("GPU mem used:", out.strip(), "MiB")

out, _ = ssh("ps aux | grep seg_inference | grep -v grep")
print("Process:", out[:200] or "NOT RUNNING")

client.close()
print("\nDone!")
