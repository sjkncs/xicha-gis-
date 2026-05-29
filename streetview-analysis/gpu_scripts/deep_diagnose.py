# -*- coding: utf-8 -*-
"""GPU 服务器深度诊断"""
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
    c = ssh()
    print("Connected!")

    # 1. 所有 conda 环境
    print("\n=== 所有 conda 环境 ===")
    out, _ = run(c, "/root/miniconda3/bin/conda env list 2>&1")
    print(out)

    # 2. 检查现有环境里的包
    print("\n=== base 环境 pip 包 ===")
    out, _ = run(c, "/root/miniconda3/bin/pip list 2>&1 | grep -iE 'torch|numpy|cv2|transform|timm|opencv|scipy' | head -30")
    print(out if out.strip() else "(无相关包)")

    # 3. 检查 venv 和 streetview_seg
    print("\n=== 其他环境 pip 包 ===")
    for env in ["venv", "streetview_seg"]:
        out, _ = run(c, f"/root/miniconda3/envs/{env}/bin/pip list 2>&1 | head -30")
        print(f"\n{env}:")
        print(out[:1000])

    # 4. 检查 autodl-tmp 和 autodl-pub 内容
    print("\n=== autodl-pub/data 目录 ===")
    out, _ = run(c, "ls -la /autodl-pub/data/ 2>&1 | head -20")
    print(out)

    print("\n=== autodl-tmp 目录 ===")
    out, _ = run(c, "ls -la /root/autodl-tmp/ 2>&1 | head -20")
    print(out)

    # 5. 检查已有的 gis_project 内容
    print("\n=== gis_project 内容 ===")
    out, _ = run(c, "find /root/gis_project -type f 2>&1 | head -30")
    print(out)

    # 6. GPU 显存
    print("\n=== GPU 实时状态 ===")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader 2>&1")
    print(out)

    # 7. 测试 base 环境的 python torch
    print("\n=== base python 测试 ===")
    out, _ = run(c, "/root/miniconda3/bin/python -c \"import sys; print(sys.executable)\" 2>&1")
    print(out)

    # 8. 测试 torch
    print("\n=== torch 测试 ===")
    out, _ = run(c, "/root/miniconda3/bin/python -c \"import torch; print('torch:', torch.__version__, 'CUDA:', torch.cuda.is_available())\" 2>&1")
    print(out if out.strip() else "torch 未安装")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
