# -*- coding: utf-8 -*-
"""GPU 服务器诊断与控制脚本"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=15, allow_agent=False, look_for_keys=False)
    return c

def run(c, cmd, timeout=30):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def main():
    print("Connecting...")
    c = ssh()
    print("Connected!\n")

    # 1. 基础信息
    print("=== 基础信息 ===")
    out, _ = run(c, "hostname; uptime; df -h / /tmp 2>&1")
    print(out)

    # 2. GPU 状态
    print("\n=== GPU 状态 ===")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>&1")
    print(out)

    # 3. 检查 conda 和 gis_ai 环境
    print("\n=== Conda 环境 ===")
    out, _ = run(c, "ls /opt/conda/bin/conda 2>&1; /opt/conda/bin/conda env list 2>&1")
    print(out)

    # 4. 检查 pip 安装
    print("\n=== pip 安装的包 ===")
    out, _ = run(c, "/opt/conda/bin/pip list 2>&1 | head -40")
    print(out)

    # 5. 检查是否已有工作目录
    print("\n=== /root 目录 ===")
    out, _ = run(c, "ls -la /root/ 2>&1")
    print(out)

    # 6. 检查 gis_project
    print("\n=== /root/gis_project ===")
    out, _ = run(c, "ls -la /root/gis_project/ 2>&1")
    print(out)

    # 7. 检查 /tmp 磁盘
    print("\n=== 磁盘空间 ===")
    out, _ = run(c, "df -h 2>&1 | head -10")
    print(out)

    # 8. 检查 GPU 进程
    print("\n=== GPU 进程 ===")
    out, _ = run(c, "nvidia-smi 2>&1 | head -20")
    print(out)

    # 9. 杀掉占用 GPU 的进程
    print("\n=== 尝试释放 GPU ===")
    out, _ = run(c, "nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>&1")
    print("当前占用进程:", out if out.strip() else "无")

    # 10. 检查 torch
    print("\n=== PyTorch 检查 ===")
    out, _ = run(c, "/opt/conda/envs/gis_ai/bin/python -c \"import torch; print(torch.__version__, torch.cuda.is_available())\" 2>&1")
    print(out if out.strip() else "gis_ai 环境不存在")

    # 11. 如果 torch 已安装，测试 GPU
    print("\n=== GPU PyTorch 测试 ===")
    out, _ = run(c, "/opt/conda/envs/gis_ai/bin/python -c \"import torch; t = torch.randn(1000,1000).cuda(); print('GPU OK:', torch.cuda.get_device_name(0))\" 2>&1")
    print(out if out.strip() else "(跳过)")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
