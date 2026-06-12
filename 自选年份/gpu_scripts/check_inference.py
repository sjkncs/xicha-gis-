# -*- coding: utf-8 -*-
"""检查推理进度和GPU状态"""
import paramiko
from pathlib import Path
import socket

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PASS = "roBbKv+ed3Vm"
REMOTE = "/root/gis_project"
VENV = "/root/venv"

def make_ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20, allow_agent=False, look_for_keys=False)
    return c

def quick_cmd(ssh_c, cmd, timeout=8):
    try:
        chan = ssh_c.get_transport().open_session()
        chan.settimeout(timeout)
        chan.exec_command(cmd)
        out = b""
        try:
            while True:
                chunk = chan.recv(4096)
                if not chunk: break
                out += chunk
        except socket.timeout:
            pass
        chan.close()
        return out.decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERR] {e}"

def main():
    ssh_c = make_ssh()
    print("=" * 55)
    print("  GPU 推理状态检查")
    print("=" * 55)

    # GPU状态
    print("\n[GPU 状态]")
    out = quick_cmd(ssh_c, "nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader", timeout=5)
    print(f"  {out.strip()}")

    # 推理进程
    print("\n[推理进程]")
    out = quick_cmd(ssh_c, "ps aux | grep seg_inference | grep -v grep", timeout=5)
    if out.strip():
        print(f"  RUNNING: {out.strip()[:200]}")
    else:
        print("  NOT RUNNING")

    # 推理日志
    print("\n[推理日志 (最后20行)]")
    out = quick_cmd(ssh_c, f"tail -20 {REMOTE}/logs/seg_inference.log", timeout=10)
    print(f"  {out.strip() or '(empty)'}")

    # 已处理的文件
    print("\n[已生成结果]")
    out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/segmentation_results/ 2>/dev/null | head -20", timeout=8)
    count_out = quick_cmd(ssh_c, f"ls {REMOTE}/data/baidu_streetview/segmentation_results/*.jpg 2>/dev/null | wc -l", timeout=8)
    print(f"  已处理图片: {count_out.strip()} 张")
    if out.strip():
        print(f"  样本文件: {out.strip()[:300]}")

    # 模型状态
    print("\n[SegFormer B3 模型]")
    out = quick_cmd(ssh_c, f"ls -lh {REMOTE}/models/hub/models--nvidia--mit-b3/snapshots/*/pytorch_model.bin 2>/dev/null || ls -lh {REMOTE}/models/hub/models--nvidia--mit-b3/snapshots/*/*.safetensors 2>/dev/null || echo NOT FOUND", timeout=8)
    print(f"  {out.strip() or 'NOT FOUND'}")

    # 服务器资源
    print("\n[服务器资源]")
    out = quick_cmd(ssh_c, "df -h / | tail -1", timeout=5)
    print(f"  磁盘: {out.strip()}")

    ssh_c.close()
    print("\n" + "=" * 55)

if __name__ == "__main__":
    main()
