#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上传修复后的 seg_inference_offline.py 并重新运行"""
import paramiko, time, os, sys
from pathlib import Path

LOCAL_SCRIPT = Path(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\seg_inference_offline.py")
REMOTE_SCRIPT = "/root/gis_project/seg_inference_offline.py"
REMOTE_DATA = "/root/gis_project/data/baidu_streetview"
REMOTE_OUT = "/root/gis_project/outputs/segmentation"
CKPT_FILE = "/root/gis_project/outputs/segmentation/checkpoint.json"

HOST = "connect.bjb1.seetacloud.com"
PORT = 37625
USER = "root"
PWD = "roBbKv+ed3Vm"

def q(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    return stdout.read().decode(errors="replace"), stderr.read().decode(errors="replace")

def main():
    print("=" * 60)
    print("1. 上传修复后的脚本 ...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=10)
    sftp = ssh.open_sftp()

    sftp.put(str(LOCAL_SCRIPT), REMOTE_SCRIPT)
    print("   脚本上传完成")
    sftp.close()

    print("2. 清理 checkpoint (重新处理全部图片) ...")
    _, _ = q(ssh, f"rm -f {CKPT_FILE}", timeout=10)
    print("   checkpoint 已清理")

    print("3. 清理旧的可视化结果 ...")
    _, _ = q(ssh, f"rm -f {REMOTE_OUT}/viz/*.png 2>/dev/null; echo done", timeout=10)
    print("   viz 目录已清理")

    print("4. 启动推理 (nohup) ...")
    cmd = (
        f"cd /root/gis_project && "
        f"source ~/venv/bin/activate && "
        f"nohup python3 {REMOTE_SCRIPT} > /root/gis_project/logs/run_seg.log 2>&1 & "
        f"echo $!"
    )
    # 使用 exec 方式避免读取 nohup 输出
    chan = ssh.get_transport().open_session()
    chan.exec_command(cmd)
    time.sleep(2)
    pid_out = chan.recv(1024).decode(errors="replace")
    chan.close()

    time.sleep(3)
    _, _ = q(ssh, "ps aux | grep seg_inference_offline | grep -v grep", timeout=10)
    print(f"   进程: {pid_out.strip() or '未找到'}")
    ssh.close()
    print("=" * 60)
    print("已启动，请运行 monitor.py 跟踪进度")

if __name__ == "__main__":
    main()
