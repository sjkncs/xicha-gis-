# -*- coding: utf-8 -*-
"""GPU 测试 + 磁盘清理"""
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

def run(c, cmd, timeout=20):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def main():
    c = ssh()

    # 1. 清理 pip 缓存
    print("[1] 清理 pip 缓存...")
    out, _ = run(c, "du -sh /root/.cache/pip 2>/dev/null")
    print(f"  清理前: {out.strip()}")
    out, _ = run(c, "rm -rf /root/.cache/pip/* 2>/dev/null; echo done")
    print(f"  清理: {out.strip()}")
    out, _ = run(c, "df -h / | tail -1")
    print(f"  清理后磁盘: {out.strip()}")

    # 2. PyTorch GPU 完整测试
    print("\n[2] PyTorch GPU 完整测试...")
    test_code = (
        "import torch; "
        "print('torch:', torch.__version__); "
        "print('CUDA available:', torch.cuda.is_available()); "
        "if torch.cuda.is_available(): "
        "    print('CUDA version:', torch.version.cuda); "
        "    print('GPU:', torch.cuda.get_device_name(0)); "
        "    t = torch.randn(1000, 1000).cuda(); "
        "    print('GPU test OK:', t.sum().item())"
    )
    # 用 ; 分隔多行命令
    out, _ = run(c, f"/root/miniconda3/bin/python -c \"{test_code}\"", timeout=30)
    print(f"  {out.strip()}")

    # 3. 内存中检查可安装的包
    print("\n[3] 检查已安装的关键包...")
    for pkg, test in [
        ("numpy", "import numpy; print(numpy.__version__)"),
        ("pillow", "from PIL import Image; print('PIL OK')"),
        ("matplotlib", "import matplotlib; print('matplotlib', matplotlib.__version__)"),
    ]:
        out, _ = run(c, f"/root/miniconda3/bin/python -c \"{test}\" 2>&1")
        status = "OK" if out.strip() and "error" not in out.lower() else "MISSING"
        print(f"  [{status}] {pkg}: {out.strip()[:80]}")

    # 4. 检查 /opt/conda 里有什么
    print("\n[4] /opt/conda 内容...")
    out, _ = run(c, "/root/miniconda3/bin/pip list 2>&1 | grep -iE 'torch|numpy|transformers|timm|opencv|scipy' | head -20")
    print(f"  {out.strip() or '无相关包'}")
    out, _ = run(c, "/opt/conda/bin/pip list 2>&1 | grep -iE 'torch|numpy|transformers|timm|opencv|scipy' | head -20")
    print(f"  /opt/conda: {out.strip() or '无'}")
    out, _ = run(c, "/opt/conda/bin/python -c \"import torch; print('torch:', torch.__version__)\" 2>&1")
    print(f"  /opt/conda torch: {out.strip()}")

    # 5. /root/venv 里有什么
    print("\n[5] /root/venv 环境...")
    out, _ = run(c, "/root/venv/bin/pip list 2>&1 | grep -iE 'torch|numpy|transformers|timm|opencv|scipy' | head -20")
    print(f"  {out.strip() or '无'}")
    out, _ = run(c, "/root/venv/bin/python -c \"import torch; print('torch:', torch.__version__)\" 2>&1")
    print(f"  venv torch: {out.strip()}")

    # 6. GPU 状态
    print("\n[6] GPU 最终状态...")
    out, _ = run(c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,driver_version --format=csv,noheader 2>&1")
    print(f"  {out.strip()}")

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
