# -*- coding: utf-8 -*-
"""GPU 服务器紧急诊断"""
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

def run(c, cmd, timeout=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    return stdout.read().decode("utf-8", errors="replace"), stderr.read().decode("utf-8", errors="replace")

def main():
    c = ssh()

    # 1. 磁盘占用分析
    print("=== 磁盘占用 (/) ===")
    out, _ = run(c, "du -h --max-depth=2 / 2>/dev/null | sort -hr | head -20")
    print(out[:2000])

    # 2. 大文件
    print("\n=== 大文件 (前20) ===")
    out, _ = run(c, "find / -type f -size +500M 2>/dev/null | head -20")
    print(out[:2000])

    # 3. PyTorch GPU 完整测试
    print("\n=== PyTorch GPU 完整测试 ===")
    out, _ = run(c,
        '/root/miniconda3/bin/python -c "'
        'import torch; '
        'print(\\"torch:\\", torch.__version__); '
        'print(\\"CUDA available:\\", torch.cuda.is_available()); '
        'if torch.cuda.is_available(): '
        '  print(\\"CUDA version:\\", torch.version.cuda); '
        '  print(\\"GPU:\\", torch.cuda.get_device_name(0)); '
        '  t = torch.randn(1000,1000).cuda(); '
        '  print(\\"GPU test OK:\\", t.sum().item())" 2>&1'
    , timeout=30)
    print(out)

    # 4. CUDA 驱动版本
    print("\n=== CUDA 驱动 ===")
    out, _ = run(c, "nvidia-smi | grep -E 'CUDA|Driver'")
    print(out)

    # 5. /autodl-pub/data 可用空间
    print("\n=== /autodl-pub/data ===")
    out, _ = run(c, "df -h /autodl-pub/data")
    print(out)

    # 6. 检查是否有 apt 缓存可以清理
    print("\n=== 清理建议 ===")
    out, _ = run(c, "apt-get clean 2>&1; rm -rf /var/lib/apt/lists/* 2>/dev/null; echo done")
    print(f"清理: {out.strip()}")

    # 7. 检查 /root 下大目录
    print("\n=== /root 大目录 ===")
    out, _ = run(c, "du -sh /root/* 2>/dev/null | sort -hr | head -10")
    print(out)

    # 8. 检查 pip 缓存
    print("\n=== pip 缓存 ===")
    out, _ = run(c, "du -sh /root/.cache/pip 2>/dev/null || echo '无pip缓存'")
    print(out)

    # 9. 确认 miniconda3 大小
    print("\n=== miniconda3 大小 ===")
    out, _ = run(c, "du -sh /root/miniconda3 2>/dev/null")
    print(out)

    # 10. /opt/conda 大小
    print("\n=== /opt/conda 大小 ===")
    out, _ = run(c, "du -sh /opt/conda 2>/dev/null || echo '无/opt/conda'")
    print(out)

    c.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
