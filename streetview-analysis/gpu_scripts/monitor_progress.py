#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每30秒检查一次推理进度，Ctrl+C停止"""
import paramiko, time, sys
from pathlib import Path

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PWD = "roBbKv+ed3Vm"

def q(client, cmd, timeout=15):
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")
    except Exception as e:
        return "", str(e)

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)

    print("开始监控 (Ctrl+C 停止)\n")
    prev_count = -1
    while True:
        # 进程
        out, _ = q(ssh, "ps aux | grep seg_inference_offline | grep -v grep | grep -v defunct")
        procs = [l for l in out.strip().split('\n') if l]
        if not procs:
            print(f"[{time.strftime('%H:%M:%S')}] 进程已结束!")
            break

        # 日志末尾 (最新处理结果)
        out, _ = q(ssh, "tail -6 /root/gis_project/logs/seg_inference_offline.log 2>/dev/null")
        lines = [l for l in out.strip().split('\n') if l]
        last_line = lines[-1] if lines else ""

        # 可视化图片数
        out, _ = q(ssh, "ls /root/gis_project/outputs/segmentation/viz/*.png 2>/dev/null | wc -l")
        viz_count = int(out.strip() or 0)

        # CSV 行数
        out, _ = q(ssh, "wc -l /root/gis_project/outputs/segmentation/seg_results.csv 2>/dev/null")
        csv_lines = out.strip().split()[0] if out.strip() else "0"

        # 从日志提取进度
        import re
        m = re.search(r'\[(\d+)/294\]', last_line)
        if m:
            current = int(m.group(1))
        else:
            m2 = re.search(r'\[(\d+)/', last_line)
            current = int(m2.group(1)) if m2 else 0

        pct = current / 294 * 100
        print(f"[{time.strftime('%H:%M:%S')}] {current}/294 ({pct:.1f}%) | viz:{viz_count} | csv行:{csv_lines} | last: {last_line[:80]}")

        if current >= 294:
            print("全部完成!")
            break
        time.sleep(30)

    # 最终状态
    print("\n=== 最终日志 ===")
    out, _ = q(ssh, "tail -10 /root/gis_project/logs/seg_inference_offline.log 2>/dev/null")
    print(out)
    ssh.close()

if __name__ == "__main__":
    main()
