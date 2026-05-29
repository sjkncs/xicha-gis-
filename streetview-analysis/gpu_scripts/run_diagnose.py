#!/usr/bin/env python3
"""探查远端 Python 环境、模型文件、transformers 路径"""
import paramiko, socket
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)

def q(cmd, t=30):
    try:
        ch = c.get_transport().open_session(); ch.settimeout(t)
        ch.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = ch.recv(65536)
                if not chunk: break
                out += chunk
        except socket.timeout: pass
        ch.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERR] {e}"

cmds = [
    "which python3 && python3 --version",
    "python3 -c 'import transformers; print(transformers.__file__)'",
    "python3 -c 'import os; print(\"HF_HOME:\", os.environ.get(\"HF_HOME\",\"unset\")); print(\"HF_HUB_OFFLINE:\", os.environ.get(\"HF_HUB_OFFLINE\",\"unset\"))'",
    "ls /root/gis_project/models/ 2>/dev/null || echo 'DIR NOT FOUND'",
    "find /root -name 'config.json' 2>/dev/null | grep -i 'segform' | head -5",
    "find /root -name 'config.json' 2>/dev/null | grep -i 'mit' | head -5",
    "conda info --envs 2>/dev/null || echo 'no conda'",
    "ls /root/venv/bin/python 2>/dev/null || echo 'no venv'",
    "python3 -m pip show transformers 2>/dev/null | head -5",
]

for cmd in cmds:
    print(f"\n$ {cmd}")
    r = q(cmd)
    print(r.strip())

c.close()
