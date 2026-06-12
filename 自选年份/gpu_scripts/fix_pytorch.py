#!/usr/bin/env python3
"""检查并安装兼容 Blackwell 架构的 PyTorch"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(cmd, timeout=120):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

# 1. 检查 GPU 架构
print("=== GPU 信息 ===")
out, _ = run("nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv,noheader")
print(out)

# 2. 检查当前 PyTorch CUDA 支持
print("\n=== 当前 PyTorch ===")
out, _ = run("python3 -c \"import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}'); print(f'SM support: {[s for s in torch.cuda.get_device_capability()]}')\" 2>&1")
print(out)

# 3. 尝试安装 nightly PyTorch with CUDA 12.6+ (支持 Blackwell)
print("\n=== 安装 nightly PyTorch ===")
# 先卸载旧版
out, err = run("pip uninstall -y torch torchvision ultralytics 2>&1", timeout=120)
print(f"卸载: {out[:200]}")
time.sleep(2)

# 安装 nightly（支持 Blackwell SM_90）
out, err = run(
    "pip install --pre torch torchvision --index-url https://download.pytorch.org/whl/nightly/cu126 2>&1",
    timeout=600
)
print(f"安装输出: {out[-500:]}")

# 4. 重新安装 ultralytics
out, err = run("pip install ultralytics 2>&1", timeout=120)
print(f"ultralytics: {out[-200:]}")

# 5. 验证
print("\n=== 验证 ===")
out, _ = run("python3 -c \"import torch; print(f'PyTorch: {torch.__version__}'); print(f'CUDA: {torch.version.cuda}'); print(f'Can use CUDA: {torch.cuda.is_available()}')\" 2>&1")
print(out)

ssh.close()
