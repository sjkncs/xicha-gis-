#!/usr/bin/env python3
import paramiko
import sys

host = "connect.bjb1.seetacloud.com"
port = 37625
username = "root"
password = "roBbKv+ed3Vm"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=username, password=password, timeout=30)

commands = [
    ("pwd & streetview dir", "cd /root/streetview_seg && pwd && ls -la"),
    ("venv packages", "cd /root/streetview_seg && source venv/bin/activate && pip list 2>/dev/null | head -30"),
    ("miniconda", "ls /root/miniconda3/bin/ 2>/dev/null | head -20"),
    ("data dirs", "find /root -maxdepth 3 -name '*.jpg' 2>/dev/null | head -5; find /root -maxdepth 3 -name '*.csv' 2>/dev/null | head -10"),
    ("disk", "df -h"),
    ("GPU tools", "which torch 2>/dev/null || which python3; ls /root/streetview_seg/venv/lib/ 2>/dev/null | head -5"),
    ("ports", "ss -tlnp 2>/dev/null | head -20"),
]

for name, cmd in commands:
    print(f"\n{'='*60}")
    print(f"# {name}")
    print('='*60)
    stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out: print(out)
    if err: print("ERR:", err)

client.close()
print("\n=== DONE ===")
