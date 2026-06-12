#!/usr/bin/env python3
import paramiko, time
HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')

def run_bg(c, cmd, logfile, timeout=30):
    stdin, stdout, stderr = c.exec_command(
        f"{cmd} > {logfile} 2>&1 & echo PID=$!", timeout=timeout
    )
    return stdout.read().decode(), stderr.read().decode()

c = ssh()

print("=" * 60)
print("升级 PyTorch 2.5 + CUDA 12.4 (RTX Blackwell 兼容)")
print("=" * 60)

# Step 1: 卸载旧PyTorch
print("\n卸载旧PyTorch...")
out, err = run(c, "pip3 uninstall -y torch torchvision torchaudio 2>&1 | tail -5")
print(out[-300:])

# Step 2: 安装新PyTorch
print("\n安装 PyTorch 2.5.1 CUDA 12.4...")
sftp = c.open_sftp()

# 写安装脚本
install_script = """#!/bin/bash
echo "=== Installing PyTorch 2.5.1 + CUDA 12.4 ===" >> /root/autodl-tmp/pytorch_install.log
date >> /root/autodl-tmp/pytorch_install.log

pip3 install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 600 >> /root/autodl-tmp/pytorch_install.log 2>&1

echo "=== Install done ===" >> /root/autodl-tmp/pytorch_install.log
date >> /root/autodl-tmp/pytorch_install.log

# Verify
/root/miniconda3/bin/python -c "import torch; print('torch='+torch.__version__+' cuda='+str(torch.cuda.is_available())+' cudnn='+str(torch.backends.cudnn.version()))" >> /root/autodl-tmp/pytorch_install.log 2>&1
/root/miniconda3/bin/python -c "import torch; x=torch.randn(100,100).cuda(); print('GPU test OK: '+torch.cuda.get_device_name(0))" >> /root/autodl-tmp/pytorch_install.log 2>&1
"""

with sftp.open("/root/autodl-tmp/install_pytorch.sh", "w") as f:
    f.write(install_script)
sftp.close()

# 后台执行安装
stdin, stdout, stderr = c.exec_command(
    "nohup bash /root/autodl-tmp/install_pytorch.sh > /root/autodl-tmp/pytorch_install.log 2>&1 & echo $!"
)
pid = stdout.read().decode().strip()
print(f"Install PID: {pid}")

# 等待安装开始
time.sleep(5)

# 监控安装进度
for i in range(30):
    out, err = run(c, f"tail -5 /root/autodl-tmp/pytorch_install.log 2>/dev/null")
    print(f"[{i*20}s] {out.strip()[:200]}")
    if "Install done" in out or "Successfully installed" in out:
        print("\n安装完成!")
        break
    time.sleep(20)

# 最终验证
print("\n最终验证:")
out, err = run(c, "/root/miniconda3/bin/python -c \"import torch; print('torch='+torch.__version__+' cuda='+str(torch.cuda.is_available())+' cudnn='+str(torch.backends.cudnn.version()))\"")
print(out.strip())
out, err = run(c, "/root/miniconda3/bin/python -c \"import torch; x=torch.randn(100,100).cuda(); print('GPU: '+torch.cuda.get_device_name(0))\"")
print(out.strip())

# GPU兼容性测试
print("\nGPU兼容性测试:")
out, err = run(c, "/root/miniconda3/bin/python -c \"import torch; print('sm:', torch.cuda.get_device_capability())\"")
print(out.strip())

c.close()
