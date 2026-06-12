#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()
tests = [
    ("HuggingFace", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://huggingface.co 2>/dev/null"),
    ("HuggingFace models", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://huggingface.co/models 2>/dev/null"),
    ("HuggingFace raw", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://huggingface.co/raw/main/README.md 2>/dev/null"),
    ("Modelscope", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://modelscope.cn 2>/dev/null"),
    ("TUNASeg", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://mirrors.tuna.tsinghua.edu.cn 2>/dev/null"),
    ("PyPI", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://pypi.tuna.tsinghua.edu.cn 2>/dev/null"),
    ("Github raw", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://raw.githubusercontent.com 2>/dev/null"),
    ("Kaggle", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://www.kaggle.com 2>/dev/null"),
    ("Google Drive", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://drive.google.com 2>/dev/null"),
    ("BaiduPCS", "curl -s --connect-timeout 5 -o /dev/null -w '%{http_code}' https://pan.baidu.com 2>/dev/null"),
    ("Nvidia NGC", "curl -s --connect-timeout 8 -o /dev/null -w '%{http_code}' https://ngc.nvidia.com 2>/dev/null"),
    ("阿里云 ModelScope", "curl -s --connect-timeout 8 -I https://modelscope.cn/models/nvidia/segformer-b0-finetuned-ade-512-512/files 2>&1 | head -3"),
]

for name, cmd in tests:
    try:
        out = run(c, cmd)
        print(f"  {name}: {out.strip()[:80]}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")
c.close()
