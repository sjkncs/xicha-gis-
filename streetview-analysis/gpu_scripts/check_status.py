#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    ("model files", "find /root/autodl-tmp/models -name '*.bin' -o -name '*.h5' 2>/dev/null | head -10"),
    ("model snapshots", "ls -lh /root/autodl-tmp/models/hub/models--nvidia--segformer-b3-finetuned-ade-512-512/snapshots/default/ 2>/dev/null"),
    ("process", "ps aux | grep seg_inference | grep -v grep"),
    ("gpu", "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader"),
    ("log tail", "tail -30 /root/gis_project/logs/seg_v3.log 2>/dev/null"),
    ("checkpoint", "cat /root/autodl-tmp/outputs/segmentation/checkpoint.json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(\"done:\", len(d.get(\"done\",[])), \"pending:\", len(d.get(\"results\",[]))' 2>/dev/null || echo 'no checkpoint'"),
]
for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {name} ===")
    print(out[:600] if out else err[:200])
    print()
client.close()
