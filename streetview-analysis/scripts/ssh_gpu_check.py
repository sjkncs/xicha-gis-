# -*- coding: utf-8 -*-
import subprocess

# Check GPU environment on remote server
cmd = [
    'sshpass', '-proBbKv+ed3Vm',
    'ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=15',
    '-p', '10244', 'root@connect.bjb1.seetacloud.com',
    'echo "=== GPU ===" && nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader && '
    'echo "=== Python ===" && python3 --version && '
    'echo "=== PyTorch ===" && python3 -c "import torch; print(f\"PyTorch: {torch.__version__}, CUDA: {torch.cuda.is_available()}\")" 2>/dev/null && '
    'echo "=== Segmentation ===" && pip3 list 2>/dev/null | grep -iE "torch|segmentation|timm|opencv|albumentations" || echo "checking..."'
]

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
try:
    out, _ = proc.communicate(timeout=60)
    print(out.decode('utf-8', errors='replace'))
except subprocess.TimeoutExpired:
    proc.kill()
    print("TIMEOUT after 60s")
except FileNotFoundError:
    print("sshpass not found, trying paramiko...")
