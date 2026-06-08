#!/usr/bin/env python3
"""检查 GPU 服务器数据完整性"""
import paramiko, sys

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"
TIMEOUT = 30

def run_cmd(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=TIMEOUT)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(f"STDERR: {err.strip()[:200]}")
    return out

try:
    print(f"连接 {HOST}:{PORT}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=TIMEOUT, banner_timeout=TIMEOUT)
    print("[OK] 连接成功")

    # 1. 磁盘空间
    print("\n=== 磁盘空间 ===")
    print(run_cmd(ssh, "df -h"))

    # 2. 目录结构
    print("\n=== /root/autodl-tmp/streetview_sim/ ===")
    out = run_cmd(ssh, "ls -la /root/autodl-tmp/streetview_sim/")
    print(out)

    # 3. 结果目录
    print("\n=== results/ ===")
    out = run_cmd(ssh, "ls /root/autodl-tmp/streetview_sim/results/ 2>/dev/null | head -20 || echo '目录不存在'")
    print(out)

    # 4. 图片数量
    print("\n=== 图片文件统计 ===")
    out = run_cmd(ssh, "find /root/autodl-tmp/streetview_sim/ -name '*.jpg' -o -name '*.png' | wc -l")
    print(f"图片总数: {out.strip()}")

    # 5. 标注图数量
    print("\n=== 标注图 ===")
    out = run_cmd(ssh, "find /root/autodl-tmp/streetview_sim/results/ -name '*_annotated*' | wc -l")
    print(f"标注图: {out.strip()}")
    out = run_cmd(ssh, "find /root/autodl-tmp/streetview_sim/results/ -name '*.jpg' | wc -l")
    print(f"JPG结果: {out.strip()}")

    # 6. JSON 结果
    print("\n=== JSON 结果文件 ===")
    out = run_cmd(ssh, "ls /root/autodl-tmp/streetview_sim/*.json 2>/dev/null || echo '无JSON'")
    print(out)

    # 7. sim_run_cpu.py 是否存在
    print("\n=== 脚本文件 ===")
    out = run_cmd(ssh, "ls /root/autodl-tmp/streetview_sim/*.py 2>/dev/null || echo '无py文件'")
    print(out)

    # 8. 结果目录大小
    print("\n=== results/ 大小 ===")
    out = run_cmd(ssh, "du -sh /root/autodl-tmp/streetview_sim/results/ 2>/dev/null || echo '无法计算'")
    print(out)

    ssh.close()
    print("\n[完成]")
except Exception as e:
    print(f"[ERROR] {e}")
    sys.exit(1)
