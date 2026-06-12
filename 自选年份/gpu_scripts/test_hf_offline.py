#!/usr/bin/env python3
"""Test HF from_pretrained with offline cache on server."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=60: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Test 1: Try from_pretrained with proper HF_HUB_CACHE
cmds = [
    ("HF env vars", "echo HF_HUB_OFFLINE=$HF_HUB_OFFLINE, HF_HUB_CACHE=$HF_HUB_CACHE"),
    ("Test from_pretrained", '''python3 << 'PYEOF'
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_CACHE"] = "/root/autodl-tmp/models"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

# Try with model_id string pointing to cache
model_id = "nvidia/segformer-b3-finetuned-ade-512-512"
try:
    print("=== Try from_pretrained with model_id ===")
    processor = AutoImageProcessor.from_pretrained(model_id, cache_dir="/root/autodl-tmp/models", local_files_only=True)
    model = AutoModelForSemanticSegmentation.from_pretrained(model_id, cache_dir="/root/autodl-tmp/models", local_files_only=True)
    print("SUCCESS! Model loaded from HF cache.")
    print("Model type:", type(model).__name__)
except Exception as e:
    print(f"FAILED: {e}")
    import traceback; traceback.print_exc()

PYEOF
'''),
    ("List hub dir", "ls -la /root/autodl-tmp/models/hub/ | head -10"),
    ("Check snapshots", "ls /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/"),
    ("Check blobs", "ls /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/blobs/ 2>/dev/null | head"),
    ("From pretrained direct path", '''python3 << 'PYEOF'
import os, json
from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

# Try with absolute path and local_files_only
snap_dir = "/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default"
print("Snapshot dir contents:", os.listdir(snap_dir))

# Read config to get architecture
with open(os.path.join(snap_dir, "config.json")) as f:
    cfg = json.load(f)
print("Config model_type:", cfg.get("model_type"))

# Try AutoConfig first
try:
    from transformers import AutoConfig
    config = AutoConfig.from_pretrained(snap_dir, local_files_only=True)
    print("AutoConfig SUCCESS:", config.model_type)
except Exception as e:
    print(f"AutoConfig FAILED: {e}")

# Try AutoImageProcessor
try:
    processor = AutoImageProcessor.from_pretrained(snap_dir, local_files_only=True)
    print("AutoImageProcessor SUCCESS")
except Exception as e:
    print(f"AutoImageProcessor FAILED: {e}")

# Try full model load
try:
    model = AutoModelForSemanticSegmentation.from_pretrained(snap_dir, local_files_only=True)
    print("AutoModel SUCCESS! Model loaded.")
except Exception as e:
    print(f"AutoModel FAILED: {e}")
    import traceback; traceback.print_exc()
PYEOF
'''),
]

for name, cmd in cmds:
    out, err = ssh(cmd)
    print(f"\n=== {name} ===")
    print(out[:600])
    if err and len(err) > 3:
        print(f"  ERR: {err[:300]}")

client.close()
