#!/usr/bin/env python3
"""Diagnose config vs weights mismatch."""
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 54111, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)
ssh = lambda cmd, t=30: (lambda s=client.exec_command(cmd, timeout=t): (s[1].read().decode().strip(), s[2].read().decode().strip()))()

diagnostics = [
    ("Config keys", "python3 -c \"\nimport json\ncfg=json.load(open('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json'))\nprint('model_type:', cfg.get('model_type','?'))\nprint('architectures:', cfg.get('architectures','?'))\nprint('depths:', cfg.get('depths','?'))\nprint('hidden_sizes:', cfg.get('hidden_sizes','?'))\n\""),
    ("Weight keys sample", "python3 -c \"\nimport torch\nsd=torch.load('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/pytorch_model.bin', map_location='cpu')\nprint('Total keys:', len(sd))\nprint('stages.*:', [k for k in sd if 'stages' in k][:3])\nprint('encoder.patch:', [k for k in sd if 'patch_embeddings' in k][:3])\n\""),
    ("HF offline dirs", "find /root/.cache/huggingface -name 'config.json' 2>/dev/null | grep -i segformer | head -5"),
    ("Config model_type", "python3 -c \"\nimport json; cfg=json.load(open('/root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/config.json')); print(cfg.get('model_type','no model_type'))\n\""),
    ("CSV sample recent", "tail -5 /root/autodl-tmp/outputs/segmentation/seg_results.csv"),
    ("Inference process", "ps aux | grep seg_inference | grep -v grep"),
]

for name, cmd in diagnostics:
    out, err = ssh(cmd)
    print(f"=== {name} ===")
    print(out[:500])
    if err and len(err) > 5:
        print(f"  ERR: {err[:200]}")
    print()

client.close()
