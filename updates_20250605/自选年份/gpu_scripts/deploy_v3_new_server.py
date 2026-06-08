#!/usr/bin/env python3
"""Deploy seg_inference_v3 to new AutoDL server (port 12996, RTX PRO 6000)"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"
PORT = 12996
USER = "root"
PW = "roBbKv+ed3Vm"

LOCAL_SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_v3_server2.py"
REMOTE_SCRIPT = "/root/gis_project/seg_inference_v3.py"
LOG_REMOTE = "/root/gis_project/logs"

def ssh_exec(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

print("=" * 60)
print("Connecting to new AutoDL server (port {})...".format(PORT))
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
print("Connected!")

# 1. Kill old processes
print("\n[1/7] Killing existing inference processes...")
out, err = ssh_exec(client, "pkill -f seg_inference 2>/dev/null; sleep 1; echo done")
print(out.strip())

# 2. Create directories
print("\n[2/7] Creating directories...")
ssh_exec(client, "mkdir -p /root/gis_project/logs /autodl-pub/data/models/hub")
print("Done")

# 3. Upload script
print("\n[3/7] Uploading seg_inference_v3.py...")
sftp = client.open_sftp()
sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
sftp.close()
print("Uploaded!")

# 4. Clear old checkpoint (force re-run with new mappings)
print("\n[4/7] Clearing old checkpoint...")
ssh_exec(client, "rm -f /root/autodl-tmp/outputs/segmentation/checkpoint.json")
print("Cleared")

# 5. Check if model exists, if not download
MODEL_DIR_REMOTE = "/root/autodl-tmp/models"
MODEL_LOCAL_CHECK = "/root/autodl-tmp/models/hub/"

print("\n[5/7] Checking model...")
out, _ = ssh_exec(client, "ls {} 2>/dev/null | head -5".format(MODEL_LOCAL_CHECK))
if "models--nvidia--segformer" in out:
    print("Model already exists:", out.strip())
else:
    print("Model not found. Downloading SegFormer B3 to {}...".format(MODEL_DIR_REMOTE))
    ssh_exec(client, "mkdir -p {}".format(MODEL_DIR_REMOTE))
    dl_cmd = (
        "cd {} && "
        "python3 -c \""
        "from huggingface_hub import snapshot_download; "
        "snapshot_download(repo_id='nvidia/segformer-b3-finetuned-ade-512-512', "
        "cache_dir='{}', local_files_only=False)"
        "\" 2>&1"
    ).format(MODEL_DIR_REMOTE, MODEL_DIR_REMOTE)
    out, err = ssh_exec(client, dl_cmd, timeout=600)
    print("Download stdout:", out[-300:] if out else "(empty)")
    print("Download stderr:", err[-300:] if err else "(empty)")
    # verify
    out2, _ = ssh_exec(client, "ls {} 2>/dev/null | head -5".format(MODEL_LOCAL_CHECK))
    print("After download:", out2.strip() or "NOT FOUND - check error above")

# 6. Check GPU status
print("\n[6/7] GPU status...")
out, _ = ssh_exec(client, "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader")
print("GPU:", out.strip())

# 7. Start inference
print("\n[7/7] Starting inference with nohup...")
start_cmd = (
    "cd /root/gis_project && "
    "python3 -u seg_inference_v3.py > logs/seg_v3.log 2>&1 &"
)
ssh_exec(client, start_cmd, timeout=10)
print("Inference started!")

time.sleep(5)

# Check log
print("\n=== Log (first 40 lines) ===")
out, _ = ssh_exec(client, "tail -40 /root/gis_project/logs/seg_v3.log")
print(out)

# Check process
print("\n=== Running processes ===")
out, _ = ssh_exec(client, "ps aux | grep seg_inference | grep -v grep")
print(out or "No process found")

client.close()
print("\n" + "=" * 60)
print("Deployment complete!")
print("Monitor: tail -f /root/gis_project/logs/seg_v3.log")
print("=" * 60)
