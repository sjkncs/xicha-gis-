#!/usr/bin/env python3
"""Check server status and data completeness."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

checks = [
    ("GPU", "nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader"),
    ("PyTorch", "python3 -c \"import torch; print('torch', torch.__version__, '| CUDA:', torch.cuda.is_available())\""),
    ("Transformers", "python3 -c \"import transformers; print('transformers', transformers.__version__)\""),
    ("Model files", "ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/"),
    ("Model size", "du -sh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/"),
    ("Image count", "find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' | wc -l"),
    ("Checkpoint", "cat /root/autodl-tmp/outputs/segmentation/checkpoint.json 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('done:', len(d.get('done',[])), 'results:', len(d.get('results',[])))\" 2>/dev/null || echo 'no checkpoint'"),
    ("CSV rows", "wc -l /root/autodl-tmp/outputs/segmentation/seg_results.csv 2>/dev/null"),
    ("Viz files", "ls /root/autodl-tmp/outputs/segmentation/viz/ 2>/dev/null | wc -l"),
    ("HF network", "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://huggingface.co 2>/dev/null"),
]

for name, cmd in checks:
    out, err = ssh(cmd)
    print(f"[{name}] {out[:300]}")
    if err and len(err) > 5:
        print(f"  ERR: {err[:100]}")

client.close()
