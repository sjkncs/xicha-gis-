# -*- coding: utf-8 -*-
import paramiko
import sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    client.connect(
        'connect.bjb1.seetacloud.com',
        port=10244,
        username='root',
        password='roBbKv+ed3Vm',
        timeout=15,
        allow_agent=False,
        look_for_keys=False
    )
    print("SSH connected!")

    # Run GPU check
    stdin, stdout, stderr = client.exec_command('nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader')
    print("=== GPU ===")
    print(stdout.read().decode())

    # Python version
    stdin, stdout, stderr = client.exec_command('python3 --version')
    print("=== Python ===")
    print(stdout.read().decode())

    # PyTorch
    stdin, stdout, stderr = client.exec_command('python3 -c "import torch; print(\'PyTorch:\', torch.__version__, \'CUDA:\', torch.cuda.is_available())"')
    print("=== PyTorch ===")
    result = stdout.read().decode()
    if result:
        print(result)
    else:
        print(stderr.read().decode())

    # Installed packages
    stdin, stdout, stderr = client.exec_command('pip3 list 2>/dev/null | grep -iE "torch|segmentation|timm|opencv|albumentations|transformers" || echo "none found"')
    print("=== Segmentation libs ===")
    print(stdout.read().decode())

    client.close()
except Exception as e:
    print(f"FAILED: {e}")
