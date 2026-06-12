#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import paramiko, time
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PWD = "roBbKv+ed3Vm"

def q(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)

    # 进程状态
    out, _ = q(ssh, "ps aux | grep seg_inference_offline | grep -v grep")
    print("=== 进程状态 ===")
    print(out or "  未找到进程")

    # 实时日志末尾
    out, _ = q(ssh, "tail -5 /root/gis_project/logs/seg_inference_offline.log 2>/dev/null || tail -5 /root/gis_project/logs/run_seg.log 2>/dev/null")
    print("\n=== 最新日志 ===")
    print(out or "  无日志")

    # 图片处理进度
    out, _ = q(ssh, "ls /root/gis_project/outputs/segmentation/viz/*.png 2>/dev/null | wc -l")
    print(f"\n=== 可视化图片数量: {out.strip()} ===")

    ssh.close()

if __name__ == "__main__":
    main()
