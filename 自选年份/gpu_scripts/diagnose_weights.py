#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

# Check local cache on server
print("=== Server local HF cache ===")
out, _ = ssh("find /root/.cache/huggingface -name 'pytorch_model.bin' -o -name '*.safetensors' 2>/dev/null | head -5")
print("HF cache models:", out[:300])

out, _ = ssh("ls -lh /root/.cache/huggingface/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/ 2>/dev/null")
print("Cache snapshot:", out[:400])

# Check how many keys are in the bin file
print("\n=== Check weight file ===")
out, _ = ssh("python3 -c \"import torch; sd=torch.load('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin', map_location='cpu'); print('Keys:', len(sd)); print('Sample:', list(sd.keys())[:5])\"")
print(out[:500])

# Check config vs weights mismatch
print("\n=== Config depths vs weights ===")
out, _ = ssh("python3 -c \"import json; cfg=json.load(open('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json')); import torch; sd=torch.load('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin', map_location='cpu'); print('Config depths:', cfg['depths']); print('Config hidden_sizes:', cfg['hidden_sizes']); print('Weight keys:', len(sd)); keys_with_stages=[k for k in sd.keys() if 'stages' in k][:3]; keys_with_encoder=[k for k in sd.keys() if 'encoder' in k and 'patch' in k][:5]; print('stages keys:', keys_with_stages); print('encoder keys:', keys_with_encoder)\"")
print(out[:600])

# Check model size
print("\n=== Model size ===")
out, _ = ssh("du -sh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/")
print(out)

client.close()
