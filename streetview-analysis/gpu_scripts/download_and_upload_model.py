#!/usr/bin/env python3
"""Download SegFormer B3 model locally, then upload to AutoDL server."""
import huggingface_hub, os, time, zipfile, paramiko, shutil
from pathlib import Path

MODEL_ID = "nvidia/segformer-b3-finetuned-ade-512-512"
LOCAL_CACHE = Path(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\model_cache")
MODEL_DEST = LOCAL_CACHE / MODEL_ID.replace("/", "--")
ZIP_FILE = LOCAL_CACHE / "segformer_b3_ade20k.zip"

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
REMOTE_MODEL_DIR = "/root/autodl-tmp/models"

print("=" * 60)
print("Step 1: Download model locally")
print("=" * 60)

LOCAL_CACHE.mkdir(parents=True, exist_ok=True)

# Check if already downloaded
if MODEL_DEST.exists():
    print(f"Model already at {MODEL_DEST}")
    sz = sum(f.stat().st_size for f in MODEL_DEST.rglob("*") if f.is_file())
    print(f"Size: {sz/1024/1024:.1f} MB")
else:
    print(f"Downloading {MODEL_ID}...")
    t0 = time.time()
    try:
        snapshot_path = huggingface_hub.snapshot_download(
            MODEL_ID,
            cache_dir=str(LOCAL_CACHE),
            local_files_only=False,
            ignore_patterns=["*.msgpack", "*.h5"]
        )
        print(f"Downloaded to: {snapshot_path}")
        print(f"Time: {time.time()-t0:.1f}s")
        sz = sum(f.stat().st_size for f in Path(snapshot_path).rglob("*") if f.is_file())
        print(f"Total size: {sz/1024/1024:.1f} MB")
    except Exception as e:
        print(f"Download error: {e}")

# Find actual model path
for root, dirs, files in os.walk(LOCAL_CACHE):
    if "segformer-b3" in root and "snapshots" in root:
        MODEL_DEST = Path(root)
        break

print(f"\nModel path: {MODEL_DEST}")
print("Files:")
for f in sorted(MODEL_DEST.glob("*")):
    print(f"  {f.name}: {f.stat().st_size/1024/1024:.1f}MB")

# Check essential files
essential = ["config.json", "pytorch_model.bin", "preprocessor_config.json"]
for e in essential:
    f = MODEL_DEST / e
    print(f"  {e}: {'FOUND' if f.exists() else 'MISSING'} ({f.stat().st_size/1024/1024:.1f}MB if found)")

print("\n" + "=" * 60)
print("Step 2: Zip model for upload")
print("=" * 60)

if ZIP_FILE.exists():
    print(f"Zip already exists: {ZIP_FILE.stat().st_size/1024/1024:.1f}MB")
else:
    print("Creating zip (this may take a minute)...")
    t0 = time.time()
    with zipfile.ZipFile(ZIP_FILE, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for f in sorted(MODEL_DEST.rglob("*")):
            if f.is_file():
                arcname = f.relative_to(MODEL_DEST.parent)
                zf.write(f, arcname)
    print(f"Zip created: {ZIP_FILE.stat().st_size/1024/1024:.1f}MB in {time.time()-t0:.1f}s")

print("\n" + "=" * 60)
print("Step 3: Upload to AutoDL server")
print("=" * 60)

print("Connecting...")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
sftp = client.open_sftp()
print("Connected!")

# Create remote dir
ssh = client.get_transport().open_session()
ssh.exec_command(f"mkdir -p {REMOTE_MODEL_DIR}")
print(f"Created remote dir: {REMOTE_MODEL_DIR}")

# Upload zip
print(f"Uploading {ZIP_FILE.stat().st_size/1024/1024:.1f}MB (this may take a few minutes)...")
t0 = time.time()
sftp.put(str(ZIP_FILE), f"{REMOTE_MODEL_DIR}/segformer_b3.zip", callback=lambda c, t: print(f"  {c/1024/1024:.1f}/{t/1024/1024:.1f}MB", end="\r"))
print(f"\nUpload done in {time.time()-t0:.1f}s")
sftp.close()

# Unzip on server
print("\nUnzipping on server...")
stdin, stdout, stderr = client.exec_command(
    f"cd {REMOTE_MODEL_DIR} && unzip -o segformer_b3.zip && rm segformer_b3.zip && ls",
    timeout=60
)
print(stdout.read().decode().strip())
err = stderr.read().decode().strip()
if err:
    print("STDERR:", err[:300])

# Verify
stdin, stdout, stderr = client.exec_command(
    f"find {REMOTE_MODEL_DIR} -name 'pytorch_model.bin' -o -name 'config.json' | head -5",
    timeout=10
)
print("Files on server:", stdout.read().decode().strip())

client.close()
print("\n" + "=" * 60)
print("Model deployment complete!")
print(f"Model location: {REMOTE_MODEL_DIR}")
print("=" * 60)
