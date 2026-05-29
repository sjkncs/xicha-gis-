#!/usr/bin/env python3
import paramiko
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
PYTHON = "/root/miniconda3/bin/python"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace')

c = ssh()

# 检查pip镜像
tests = [
    ("TUNA PyTorch", "curl -s --connect-timeout 5 -I https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/ 2>&1 | head -2"),
    ("TUNA files", "curl -s --connect-timeout 5 -I https://mirrors.tuna.tsinghua.edu.cn/pypi/packages/linux-x86_64/torch-2.1.0-1-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl 2>&1 | grep -E 'HTTP|Location' | head -3"),
    ("modelscope models", "curl -s --connect-timeout 10 'https://modelscope.cn/api/v1/models/nvidia/segformer-b0-finetuned-ade-512-512' 2>&1 | head -5"),
    ("modelscope segformers", "curl -s --connect-timeout 10 'https://modelscope.cn/api/v1/models?Name=segformer' 2>&1 | head -3"),
    ("modelscope download test", "curl -s --connect-timeout 15 'https://modelscope.cn/models/nvidia/segformer-b0-finetuned-ade-512-512/summary' 2>&1 | head -10"),
]

for name, cmd in tests:
    try:
        out = run(c, cmd)
        print(f"  {name}: {out.strip()[:300]}")
    except Exception as e:
        print(f"  {name}: ERROR {e}")

# 试试通过pip安装transformers（用清华源）
print("\nInstalling transformers (TUNA mirror)...")
run(c, "pip3 install transformers -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 120 2>&1 | tail -5", timeout=180)

# 验证
out = run(c, PYTHON + ' -c "import transformers; print(transformers.__version__)" 2>&1')
print("transformers:", out.strip())

# 检查Ade20K数据
out = run(c, "ls /autodl-pub/data/ADEChallengeData2016/*.zip")
print("ADE20K zips:", out.strip())

c.close()
