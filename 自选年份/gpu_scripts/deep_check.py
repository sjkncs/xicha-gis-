#!/usr/bin/env python3
import paramiko

HOST, PORT, USER, PW = "connect.bjb1.seetacloud.com", 12996, "root", "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PW, timeout=20, allow_agent=False, look_for_keys=False)

cmds = [
    ("model dir tree", "find /root/autodl-tmp/models -maxdepth 5 -type f 2>/dev/null | head -20"),
    ("hub dir", "ls -laR /root/autodl-tmp/models/ 2>/dev/null | head -40"),
    ("full log", "cat /root/gis_project/logs/seg_v3.log 2>/dev/null"),
    ("any python processes", "ps aux | grep python | grep -v grep"),
]
for name, cmd in cmds:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace").strip()
    err = stderr.read().decode("utf-8", errors="replace").strip()
    print(f"=== {name} ===")
    print(out[:800] if out else err[:300])
    print()
client.close()
