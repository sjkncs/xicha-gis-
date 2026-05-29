#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60, allow_agent=False)
    return c

print("=" * 60)
print("Step 1: 添加清华conda/pip镜像")
print("=" * 60)
c = ssh()

# 配置pip镜像
stdin, stdout, stderr = c.exec_command(
    "pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && echo 'pip mirror OK'"
)
print(stdout.read().decode())

# 配置conda镜像
stdin, stdout, stderr = c.exec_command(
    "/root/miniconda3/bin/conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main && "
    "/root/miniconda3/bin/conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free && "
    "/root/miniconda3/bin/conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch && "
    "/root/miniconda3/bin/conda config --set show_channel_urls yes && echo 'conda mirror OK'"
)
print(stdout.read().decode())
c.close()

print("\n" + "=" * 60)
print("Step 2: 检查PyTorch镜像可用性")
print("=" * 60)
c = ssh()

# 检查TUNA PyTorch
stdin, stdout, stderr = c.exec_command(
    "curl -s --connect-timeout 10 -I https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/pytorch/ 2>&1 | head -3"
)
out = stdout.read().decode()
print("TUNA PyTorch:", out[:100])

# 检查pip install torch是否能找到
stdin, stdout, stderr = c.exec_command(
    "pip3 download torch --no-deps -d /tmp/torch_check -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1 | head -5",
    timeout=30
)
out = stdout.read().decode()
print("pip torch check:", out[:200])
c.close()

print("\n" + "=" * 60)
print("Step 3: 安装PyTorch (CUDA 12.1)")
print("=" * 60)
c = ssh()

# 先试试conda安装
print("Trying conda install...")
stdin, stdout, stderr = c.exec_command(
    "cd /root && /root/miniconda3/bin/conda install -y pytorch torchvision pytorch-cuda=12.1 -c pytorch -c nvidia 2>&1 | tail -10",
    timeout=900
)
out = stdout.read().decode()
print(out[-800:] if len(out) > 800 else out)

# 验证
stdin, stdout, stderr = c.exec_command(
    "python3 -c 'import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"no GPU\")'"
)
out = stdout.read().decode()
print("\n验证:", out.strip())

c.close()
