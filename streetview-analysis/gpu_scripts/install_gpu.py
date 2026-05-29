# -*- coding: utf-8 -*-
"""GPU 服务器环境安装 - 后台运行版
将大安装任务拆分为独立步骤，用文件标记进度"""
import paramiko
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE_WORK = "/root/gis_project"
REMOTE_SCRIPTS = f"{REMOTE_WORK}/gpu_scripts"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

def put(c, local_path, remote_path):
    s = c.open_sftp()
    s.put(str(local_path), remote_path)
    s.close()
    print(f"  [上传] {Path(local_path).name}")

def main():
    print("=" * 60)
    print("GPU 服务器环境安装")
    print("=" * 60)

    c = ssh()
    print("Connected!")

    # 1. 检查当前状态
    print("\n[1] 检查当前状态...")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used --format=csv,noheader 2>&1")
    print(f"  GPU: {out.strip()}")

    out, _ = run(c, "/root/miniconda3/bin/python -c \"import torch; print('torch', torch.__version__)\" 2>&1")
    print(f"  torch: {out.strip()}")

    # 2. 配置 pip 镜像
    print("\n[2] 配置 pip 镜像...")
    run(c, 'pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple')
    run(c, 'pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn')

    # 3. 检查是否已完成某个步骤
    STEPS = ["step2_pytorch", "step3_core", "step4_dl", "step5_3d"]
    for s in STEPS:
        out, _ = run(c, f"cat {REMOTE_SCRIPTS}/{s}.done 2>/dev/null || echo 'not_done'")
        print(f"  {s}: {out.strip()}")

    # 4. 执行 PyTorch 安装 (用 nohup 后台运行，避免超时)
    print("\n[3] 启动 PyTorch 2.5 安装 (后台运行)...")

    # 先写一个独立安装脚本
    install_script = """#!/bin/bash
set -e
LOG=/root/gis_project/gpu_scripts/step2_pytorch.log
exec > $LOG 2>&1
echo "开始安装 PyTorch 2.5: $(date)"

# 配置镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip config set global.trusted-host https://pypi.tuna.tsinghua.edu.cn
pip install --upgrade pip setuptools wheel

# 卸载旧 PyTorch
pip uninstall -y torch torchvision torchaudio 2>/dev/null || true

# 安装 PyTorch 2.5
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cu124

# 验证
python -c "import torch; print(f'torch:{torch.__version__} CUDA:{torch.cuda.is_available()}')"

echo "PyTorch 安装完成: $(date)"
touch /root/gis_project/gpu_scripts/step2_pytorch.done
"""
    sftp = c.open_sftp()
    sftp.putfo(__file__ if False else __file__.replace("\\", "/").rsplit("/", 1)[0] + "/_pytorch_install.sh",
               f"{REMOTE_SCRIPTS}/_pytorch_install.sh")

    # 直接用 heredoc 上传脚本
    encoded_script = install_script.replace("'", "'\"'\"'")
    cmd = f"cat > {REMOTE_SCRIPTS}/_pytorch_install.sh << 'EOF_SCRIPT'\n{install_script}\nEOF_SCRIPT"
    run(c, cmd, timeout=10)

    # 赋予执行权限
    run(c, f"chmod +x {REMOTE_SCRIPTS}/_pytorch_install.sh")

    # 后台运行
    print("  启动 nohup bash ...")
    out, err = run(c, f"cd {REMOTE_SCRIPTS} && nohup bash _pytorch_install.sh > _pytorch_install.out 2>&1 &", timeout=10)
    print(f"  nohup 结果: {out.strip() or '已后台启动'}")

    # 等待 30 秒后检查
    print("\n  等待 30 秒后检查进度...")
    import time; time.sleep(30)

    out, _ = run(c, f"cat {REMOTE_SCRIPTS}/_pytorch_install.out 2>&1 | tail -10")
    print(f"  当前进度:\n{out.strip()}")

    # 检查 nohup 进程
    out, _ = run(c, f"ps aux | grep _pytorch_install | grep -v grep | head -3")
    print(f"  进程: {out.strip() or '无（可能已结束）'}")

    # 如果没完成，告诉用户
    out, _ = run(c, f"test -f {REMOTE_SCRIPTS}/step2_pytorch.done && echo 'done' || echo 'running'")
    if "done" in out:
        print("\n  PyTorch 安装已完成!")
        # 验证
        out, _ = run(c, "/root/miniconda3/bin/python -c \"import torch; print(f'torch:{torch.__version__} CUDA:{torch.cuda.is_available()}')\"")
        print(f"  {out.strip()}")
    else:
        print("\n  PyTorch 安装仍在进行中")
        print(f"  查看日志: cat {REMOTE_SCRIPTS}/_pytorch_install.out")
        print("  稍后再运行 diagnose_gpu.py 检查结果")

    c.close()
    print("\nDone. 请稍后运行 python gpu_scripts/diagnose_gpu.py 检查结果")

if __name__ == "__main__":
    main()
