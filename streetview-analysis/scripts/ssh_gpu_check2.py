# -*- coding: utf-8 -*-
import subprocess

# Use plink (PuTTY) which supports -pw flag
cmd = [
    'plink', '-pw', 'roBbKv+ed3Vm',
    '-o', 'StrictHostKeyChecking=no', '-o', 'ConnectTimeout=15',
    '-P', '10244', 'root@connect.bjb1.seetacloud.com',
    'echo "=== GPU ===" && nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>&1 && '
    'echo "=== Python ===" && python3 --version && '
    'echo "=== PyTorch ===" && python3 -c "import torch; print(\"PyTorch:\", torch.__version__, \"CUDA:\", torch.cuda.is_available())" 2>/dev/null || echo "no torch" && '
    'echo "=== Segmentation libs ===" && pip3 list 2>/dev/null | grep -iE "torch|segmentation|timm|opencv|albumentations|transformers" || echo "none found"'
]

proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
try:
    out, _ = proc.communicate(timeout=60)
    print(out.decode('utf-8', errors='replace'))
except subprocess.TimeoutExpired:
    proc.kill()
    print("TIMEOUT after 60s")
except FileNotFoundError:
    print("plink not found. Trying paramiko...")
    # Fallback: try paramiko
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('connect.bjb1.seetacloud.com', port=10244, username='root',
                    password='roBbKv+ed3Vm', timeout=15)
        stdin, stdout, stderr = ssh.exec_command('nvidia-smi; python3 --version')
        print(stdout.read().decode())
        ssh.close()
    except Exception as e:
        print(f"paramiko failed: {e}")
