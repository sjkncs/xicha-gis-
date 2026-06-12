# -*- coding: utf-8 -*-
"""GPU 云服务器环境诊断 + 依赖检查"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS,
                  timeout=15, allow_agent=False, look_for_keys=False)
    return client

def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out.strip() or err.strip()

try:
    print("Connecting...")
    client = ssh_connect()
    print("Connected!\n")

    checks = [
        ("=== 1. GPU 信息 ===",
         "nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version,compute_cap "
         "--format=csv,noheader 2>&1"),
        ("=== 2. GPU 状态 ===",
         "nvidia-smi -L 2>&1"),
        ("=== 3. GPU 利用率 ===",
         "nvidia-smi --query-gpu=utilization.gpu,utilization.memory,memory.used,memory.free "
         "--format=csv,noheader 2>&1"),
        ("=== 4. Python 版本 ===",
         "python3 --version 2>&1"),
        ("=== 5. PyTorch + CUDA ===",
         'python3 -c "import torch; print(f\'PyTorch:{torch.__version__} CUDA:{torch.cuda.is_available()} v{torch.version.cuda}\')" 2>&1'),
        ("=== 6. transformers ===",
         'python3 -c "import transformers; print(\'transformers:\', transformers.__version__)" 2>&1'),
        ("=== 7. timm ===",
         'python3 -c "import timm; print(\'timm:\', timm.__version__)" 2>&1'),
        ("=== 8. opencv ===",
         'python3 -c "import cv2; print(\'opencv:\', cv2.__version__)" 2>&1'),
        ("=== 9. scipy ===",
         'python3 -c "import scipy; print(\'scipy:\', scipy.__version__)" 2>&1'),
        ("=== 10. numpy ===",
         'python3 -c "import numpy; print(\'numpy:\', numpy.__version__)" 2>&1'),
        ("=== 11. PIL ===",
         'python3 -c "from PIL import Image; print(\'PIL OK\')" 2>&1'),
        ("=== 12. COLMAP ===",
         "which colmap 2>&1; colmap --version 2>&1 || echo 'colmap not found'"),
        ("=== 13. CUDA 版本 ===",
         "nvcc --version 2>&1 || echo 'nvcc not found'"),
        ("=== 14. pip torch ===",
         "pip3 list 2>&1 | grep -iE '^torch' | head -10"),
        ("=== 15. pip 关键包 ===",
         "pip3 list 2>&1 | grep -iE 'segmentation|timm|transformers|diffusers|accelerate|PLY|albumentations|scikit' | head -20"),
        ("=== 16. 磁盘空间 ===",
         "df -h / /workspace /home /tmp 2>&1 | head -10"),
        ("=== 17. 内存 ===",
         "free -h 2>&1"),
        ("=== 18. CPU ===",
         "lscpu 2>&1 | grep -E 'Model name|CPU\(s\)|Thread|Core|Socket'"),
        ("=== 19. OS ===",
         "cat /etc/os-release 2>&1 | head -8"),
        ("=== 20. pip 所有包 ===",
         "pip3 list 2>&1 | head -60"),
    ]

    for title, cmd in checks:
        print(title)
        result = run(client, cmd)
        print(result if result else "(无输出)")
        print()

    client.close()
    print("Done.")

except paramiko.ssh_exception.AuthenticationException:
    print("Auth failed! Wrong password?")
except Exception as e:
    print(f"Error: {e}")
