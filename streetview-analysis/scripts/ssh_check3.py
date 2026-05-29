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
    # GPU进程检查
    ("GPU processes", "nvidia-smi; echo '---PROCESSES---'; ps aux | grep -iE 'python|jupyter|tensorboard|train' | grep -v grep | head -20"),
    # 搜索ADE20K数据
    ("ADE20K dir", "ls -la /autodl-pub/data/ADEChallengeData2016/ 2>/dev/null"),
    # 搜索所有模型权重
    ("search models anywhere", "find /autodl-pub -maxdepth 5 -name '*.pth' -o -name '*.pt' -o -name '*.safetensors' 2>/dev/null | head -30"),
    # 搜索SegFormer相关
    ("search segformer", "find /autodl-pub -maxdepth 6 -iname '*segform*' 2>/dev/null | head -20; find /root -maxdepth 5 -iname '*segform*' 2>/dev/null | head -20"),
    # 检查pip/conda
    ("pip3 torch check", "python3 -c 'import torch; print(torch.__version__)' 2>&1"),
    ("miniconda torch", "/root/miniconda3/bin/python -c 'import torch; print(torch.__version__)' 2>&1"),
    ("pip3 list short", "pip3 list 2>/dev/null | head -40"),
    # 查找街景数据
    ("find images", "find /autodl-pub -maxdepth 4 -type d -name '*street*' -o -type d -name '*streetview*' -o -type d -name '*baidu*' 2>/dev/null | head -20; find /root -maxdepth 4 -type d -name '*street*' 2>/dev/null | head -20"),
    # 检查ADE20K结构
    ("ADE20K training", "ls /autodl-pub/data/ADEChallengeData2016/annotations/ 2>/dev/null; ls /autodl-pub/data/ADEChallengeData2016/images/ 2>/dev/null | head -5"),
    # 网络测试
    ("pip mirror", "pip3 install torch --index-url https://download.pytorch.org/whl/cu121 2>&1 | head -5"),
    # GPU计算能力
    ("GPU arch", "nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv 2>/dev/null"),
    # kill gpu processes?
    ("kill python", "kill -0 $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null) 2>/dev/null; echo 'gpu_pids:' $(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null)"),
]

for name, cmd in commands:
    print(f"\n# {name}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if out.strip(): print(out[:1000])
    if err.strip() and 'Warning' not in err[:50]: print("ERR:", err[:200])

client.close()
print("\n=== DONE ===")
