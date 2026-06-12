#!/usr/bin/env python3
import paramiko
host = "connect.bjb1.seetacloud.com"
port = 37625
username = "root"
password = "roBbKv+ed3Vm"
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(host, port=port, username=username, password=password, timeout=30)

commands = [
    ("autodl-tmp", "ls -la /root/autodl-tmp/ 2>/dev/null; ls -la /autodl-tmp/ 2>/dev/null"),
    ("autodl-pub data", "ls -la /autodl-pub/data/ 2>/dev/null | head -30"),
    ("models dir", "ls -la /root/streetview_seg/models/ 2>/dev/null"),
    ("data dir", "ls -la /root/streetview_seg/data/ 2>/dev/null"),
    ("conda envs", "cd /root/miniconda3 && ./bin/conda info --envs 2>/dev/null || /root/miniconda3/bin/conda info --envs"),
    ("system python packages", "pip3 list 2>/dev/null | grep -iE 'torch|transformers|torchvision|opencv|pillow|numpy'"),
    ("streetview_seg content", "find /root/streetview_seg -type f 2>/dev/null"),
    ("huggingface cache", "ls ~/.cache/huggingface/ 2>/dev/null; ls ~/.cache/torch/ 2>/dev/null"),
    ("net check", "curl -s --connect-timeout 5 https://huggingface.co --max-time 10 -o /dev/null -w '%{http_code}' 2>/dev/null || echo 'HuggingFace unreachable'"),
]

for name, cmd in commands:
    print(f"\n# {name}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=20)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out)
    if err.strip(): print("ERR:", err[:200])

client.close()
print("\n=== DONE ===")
