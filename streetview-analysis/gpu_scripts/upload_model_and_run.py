#!/usr/bin/env python3
"""Upload local SegFormer B3 model to AutoDL server, then restart inference."""
import paramiko, zipfile, os, time
from pathlib import Path

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"

LOCAL_SNAPSHOT = Path(r"C:\Users\Administrator\.cache\huggingface\hub\models--nvidia--segformer-b3-finetuned-ade-512-512\snapshots\a820c29fc1e53723079d94ca0e09a14d2657fae6")
REMOTE_MODEL_DIR = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512"
REMOTE_SCRIPT = "/root/gis_project/seg_inference_v3.py"
REMOTE_LOG = "/root/gis_project/logs/seg_v3.log"
LOCAL_ZIP = Path(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_segformer_b3.zip")

INFERENCE_SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v3_server2.py"

print("=" * 60)
print("Step 1: Create zip of model snapshot")
print("=" * 60)
print(f"Source: {LOCAL_SNAPSHOT}")

if LOCAL_ZIP.exists():
    print(f"Zip already exists: {LOCAL_ZIP.stat().st_size/1024/1024:.1f}MB")
else:
    print("Creating zip (362MB)...")
    t0 = time.time()
    with zipfile.ZipFile(LOCAL_ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        # Zip so it extracts directly into snapshots/default/
        for f in sorted(LOCAL_SNAPSHOT.rglob("*")):
            if f.is_file():
                arcname = "snapshots/default/" + f.name
                zf.write(f, arcname)
    print(f"Zip done: {LOCAL_ZIP.stat().st_size/1024/1024:.1f}MB in {time.time()-t0:.1f}s")

print()
print("=" * 60)
print("Step 2: Upload model zip to AutoDL")
print("=" * 60)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()
print("Connected!")

# Create remote dir
print(f"Creating remote dir: {REMOTE_MODEL_DIR}")
ssh_exec = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()
ssh_exec(f"mkdir -p {REMOTE_MODEL_DIR}")

# Upload zip
zip_sz = LOCAL_ZIP.stat().st_size / 1024 / 1024
print(f"Uploading {zip_sz:.1f}MB (may take 1-3min)...")
t0 = time.time()
def progress_cb(c, t):
    pct = c/t*100 if t > 0 else 0
    print(f"\r  {c/1024/1024:.1f}/{t/1024/1024:.1f}MB ({pct:.0f}%)", end="", flush=True)
sftp.put(str(LOCAL_ZIP), f"{REMOTE_MODEL_DIR}/..zipname__segformer_b3.zip", callback=progress_cb)
print(f"\nUpload done in {time.time()-t0:.1f}s")
sftp.close()

print()
print("=" * 60)
print("Step 3: Extract zip on server")
print("=" * 60)
stdin, stdout, stderr = client.exec_command(
    f"cd /root/autodl-tmp/models && "
    f"rm -rf hub && mkdir -p hub && "
    f"cd hub && "
    f"unzip -o ..zipname__segformer_b3.zip && rm ..zipname__segformer_b3.zip && "
    f"ls -la hub/ && ls -la hub/snapshots/default/",
    timeout=60
)
print(stdout.read().decode().strip())
err = stderr.read().decode().strip()
if err:
    print("STDERR:", err[:300])

# Verify model files
print()
print("=" * 60)
print("Step 4: Verify model files")
print("=" * 60)
stdin, stdout, stderr = client.exec_command(
    f"find {REMOTE_MODEL_DIR}/snapshots/default -type f | head -10",
    timeout=10
)
files = stdout.read().decode().strip()
print("Model files:", files)

# Check essential files
essential = ["pytorch_model.bin", "config.json", "preprocessor_config.json"]
all_ok = True
for e in essential:
    stdin, stdout, stderr = client.exec_command(f"ls -lh {REMOTE_MODEL_DIR}/snapshots/default/{e} 2>&1", timeout=5)
    result = stdout.read().decode().strip()
    print(f"  {e}: {result if result else 'MISSING'}")
    if not result or "No such" in result:
        all_ok = False

print()
print("=" * 60)
print("Step 5: Fix inference script to use snapshot path")
print("=" * 60)

# Read and fix the script - use the MODEL_DIR as repo_id
with open(INFERENCE_SCRIPT, "r", encoding="utf-8") as f:
    script_content = f.read()

# Fix: load from repo_id pointing to MODEL_DIR cache dir
old_load = '''def load_model():
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
    log("Loading model from: {}".format(MODEL_LOCAL))
    t0 = time.time()
    processor = SegformerImageProcessor.from_pretrained(str(MODEL_LOCAL), local_files_only=True)
    model = SegformerForSemanticSegmentation.from_pretrained(str(MODEL_LOCAL), local_files_only=True)'''

new_load = '''def load_model():
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
    log("Loading model from: {}".format(MODEL_LOCAL))
    t0 = time.time()
    # Use repo_id pointing to cache dir so transformers can find metadata
    processor = SegformerImageProcessor.from_pretrained(
        str(MODEL_DIR), local_files_only=True)
    model = SegformerForSemanticSegmentation.from_pretrained(
        str(MODEL_DIR), local_files_only=True)'''

if old_load in script_content:
    script_content = script_content.replace(old_load, new_load)
    print("Fixed load_model() to use MODEL_DIR as repo_id")
else:
    print("WARNING: Could not find exact load_model pattern, checking current...")
    # Just show the relevant section
    for line in script_content.split('\n'):
        if 'load_model' in line or 'from_pretrained' in line or 'MODEL_LOCAL' in line:
            print(f"  {line}")

with open(INFERENCE_SCRIPT, "w", encoding="utf-8") as f:
    f.write(script_content)
print("Script updated!")

# Re-upload fixed script
print()
print("=" * 60)
print("Step 6: Upload fixed script")
print("=" * 60)
sftp = client.open_sftp()
sftp.put(INFERENCE_SCRIPT, REMOTE_SCRIPT)
sftp.close()
print("Uploaded!")

# Clear checkpoint
print()
print("=" * 60)
print("Step 7: Clear checkpoint and GPU memory")
print("=" * 60)
ssh_exec = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()
ssh_exec("rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
ssh_exec("nvidia-smi --gpu-reset 2>&1 || echo 'GPU reset not needed'")
print("Checkpoint cleared")

# Start inference
print()
print("=" * 60)
print("Step 8: Start inference")
print("=" * 60)
start_cmd = (
    "cd /root/gis_project && "
    "python3 -u seg_inference_v3.py > logs/seg_v3.log 2>&1 &"
)
client.exec_command(start_cmd, timeout=10)
print("Inference started!")
time.sleep(5)

# Check log
print()
print("=" * 60)
print("Step 9: Verify inference started")
print("=" * 60)
stdin, stdout, stderr = client.exec_command(f"tail -30 {REMOTE_LOG}", timeout=10)
log_out = stdout.read().decode().strip()
print(log_out)

stdin, stdout, stderr = client.exec_command("ps aux | grep seg_inference | grep -v grep", timeout=5)
proc_out = stdout.read().decode().strip()
print("Process:", proc_out or "NOT RUNNING")

client.close()

print()
print("=" * 60)
print("DONE! Monitor with:")
print(f"  ssh -p {PORT} {USER}@{HOST}")
print(f"  tail -f {REMOTE_LOG}")
print("=" * 60)
