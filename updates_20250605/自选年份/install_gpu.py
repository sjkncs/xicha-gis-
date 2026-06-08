#!/usr/bin/env python3
import paramiko, time, sys
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60, allow_agent=False)
    return c

def run_bg(c, cmd, timeout=600):
    """后台运行命令"""
    channel = c.get_transport().open_session()
    channel.get_pty()
    channel.exec_command(cmd)
    return channel

print("=" * 60)
print("安装 PyTorch + Transformers (清华镜像)")
print("=" * 60)
c = ssh()

# 安装PyTorch (CUDA 12.1)
print("Installing PyTorch (CUDA 12.1)...")
stdin, stdout, stderr = c.exec_command(
    "pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu121 "
    "-i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 600 2>&1 | tail -5",
    timeout=900
)
out = stdout.read().decode('utf-8', errors='replace')
print(out[-500:] if len(out) > 500 else out)

# 验证
stdin, stdout, stderr = c.exec_command("python3 -c 'import torch; print(torch.__version__); print(torch.cuda.is_available())'")
out = stdout.read().decode('utf-8', errors='replace')
print("\nPyTorch验证:", out.strip())

# 安装transformers等
print("\nInstalling transformers, pillow, matplotlib...")
stdin, stdout, stderr = c.exec_command(
    "pip3 install transformers pillow matplotlib scikit-image -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 600 2>&1 | tail -5",
    timeout=900
)
out = stdout.read().decode('utf-8', errors='replace')
print(out[-500:] if len(out) > 500 else out)

# 最终验证
stdin, stdout, stderr = c.exec_command(
    "python3 -c 'import torch; import transformers; import PIL; print(f\"torch={torch.__version__} cuda={torch.cuda.is_available()}\"); print(f\"transformers={transformers.__version__}\")'"
)
out = stdout.read().decode('utf-8', errors='replace')
print("\n最终验证:", out.strip())

c.close()
print("\n安装完成!")
