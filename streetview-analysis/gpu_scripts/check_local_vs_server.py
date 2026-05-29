#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Check server model exact size
out, _ = ssh("du -sh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin")
print("Server pytorch_model.bin:", out)

out, _ = ssh("md5sum /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin")
print("Server MD5:", out[:100])

# Check transformers version on server
out, _ = ssh("pip show transformers | head -5")
print("transformers:", out[:100])

out, _ = ssh("python3 -c \"import transformers; print(transformers.__version__)\"")
print("Version:", out)

# Check total keys
out, _ = ssh("python3 -c \"import torch; sd=torch.load('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin', map_location='cpu'); print('Total keys:', len(sd)); missing_0=[k for k in list(sd.keys())[:3]]; print('First keys:', missing_0)\"")
print(out[:500])

# Check local cache - what HF downloaded
import os
LOCAL_HUB = os.path.expanduser("~/.cache/huggingface/hub")
print(f"\nLocal HF hub: {LOCAL_HUB}")
if os.path.exists(LOCAL_HUB):
    for root, dirs, files in os.walk(LOCAL_HUB):
        for f in files:
            fp = os.path.join(root, f)
            sz = os.path.getsize(fp)
            print(f"  {fp[-80:]}: {sz/1024/1024:.1f}MB")
else:
    print("  Not found")

# Check the models--nvidia--segformer-b3 path
SNAP_PATH = r"C:\Users\Administrator\.cache\huggingface\hub\models--nvidia--segformer-b3-finetuned-ade-512-512\snapshots\a820c29fc1e53723079d94ca0e09a14d2657fae6"
print(f"\nSnapshot path exists: {os.path.exists(SNAP_PATH)}")
if os.path.exists(SNAP_PATH):
    files = os.listdir(SNAP_PATH)
    print(f"Files: {files}")
    for f in files:
        fp = os.path.join(SNAP_PATH, f)
        sz = os.path.getsize(fp)
        print(f"  {f}: {sz/1024/1024:.1f}MB")

client.close()
