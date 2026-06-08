#!/usr/bin/env python3
"""检查依赖安装 + 确认可用模型"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

# 检查依赖
print("=== 依赖包检查 ===")
packages = ["transformers", "cv2", "albumentations", "scipy", "sklearn", "pandas", "PIL", "skimage", "matplotlib", "numpy"]
for pkg in packages:
    import_name = pkg.replace("-", "_").replace("cv2", "cv2").replace("sklearn", "sklearn").replace("PIL", "PIL")
    cmd = f'{PYTHON_SYS} -c "import {import_name}; print({import_name}.__version__)" 2>&1'
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if err and "ModuleNotFoundError" in err:
        print(f"  {pkg}: MISSING")
    elif "ERROR" in out or "Traceback" in out:
        print(f"  {pkg}: ERROR")
    else:
        print(f"  {pkg}: OK ({out})")

# 检查pip进程
stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip3 install' | grep -v grep", timeout=10)
pip = stdout.read().decode().strip()
print(f"\nPIP进程: {pip[:100] if pip else '无'}")

# 检查日志
stdin, stdout, stderr = c.exec_command("tail -5 /root/autodl-tmp/deps.log 2>/dev/null", timeout=10)
log = stdout.read().decode().strip()
print(f"日志: {log[:200]}")

# 检查服务器已有的图片数据
print("\n=== 服务器已有数据 ===")
stdin, stdout, stderr = c.exec_command("find /root /autodl-tmp /data -name '*.jpg' 2>/dev/null | head -10", timeout=15)
existing_imgs = stdout.read().decode('utf-8', errors='replace').strip()
print(existing_imgs if existing_imgs else "未找到图片")

# 检查datasets
stdin, stdout, stderr = c.exec_command("ls /autodl-pub/data/ 2>/dev/null | head -20", timeout=10)
datasets = stdout.read().decode('utf-8', errors='replace').strip()
print(f"\n公开数据:\n{datasets}")

# 检查CPU核心数
stdin, stdout, stderr = c.exec_command("nproc && free -h | grep Mem", timeout=10)
print(f"\n硬件:\n{stdout.read().decode()}")

sftp.close()
c.close()
