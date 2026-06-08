#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    ("autodl-pub", "ls /root/autodl-pub/ 2>&1"),
    ("huggingface cache", "ls /root/.cache/huggingface/hub/ 2>&1"),
    ("find baidu", "find /root/autodl-pub/ -maxdepth 3 -type d 2>/dev/null | head -20"),
    ("find segformer model", "find /root/ -name '*segformer*' -type d 2>/dev/null | head -5"),
    ("hf cache size", "du -sh /root/.cache/huggingface/ 2>&1 || echo 0"),
    ("venv python", "source /root/venv/bin/activate && which python && pip list 2>/dev/null | grep -i -E 'torch|transformers|numpy|pillow'"),
    ("gis_project detail", "ls -la /root/gis_project/ 2>&1"),
]
for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f"=== {name} ===")
    print(out[:600] if out else err[:200])
    print()

client.close()
