#!/usr/bin/env python3
"""
安装 Grounding DINO 模型到远程服务器
"""
import paramiko, os, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = c.open_sftp()

REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"
GDINO_DIR = f"{REMOTE_DIR}/groundingdino"
def ensure_dir(sftp, path):
    """递归创建目录"""
    dirs = []
    while path and path != '/':
        dirs.append(path)
        path = os.path.dirname(path)
    dirs.reverse()
    for d in dirs:
        try:
            sftp.stat(d)
        except IOError:
            sftp.mkdir(d)

ensure_dir(sftp, GDINO_DIR)
ensure_dir(sftp, f"{REMOTE_DIR}/grounding_results")

commands = [
    ("创建config目录", "mkdir -p /root/autodl-tmp/streetview_analysis/groundingdino"),

    ("克隆 GroundingDINO 仓库", 
     "cd /root/autodl-tmp/streetview_analysis && "
     "git clone https://github.com/IDEA-Research/GroundingDINO.git groundingdino_repo 2>&1 || echo 'clone done'"),

    ("复制config.py", 
     "cp /root/autodl-tmp/streetview_analysis/groundingdino_repo/groundingdino/config.py "
     "/root/autodl-tmp/streetview_analysis/groundingdino/config.py"),

    ("下载模型权重 (~2.7GB)", 
     "cd /root/autodl-tmp/streetview_analysis/groundingdino && "
     "wget -q --show-progress "
     "-O groundingdino_swint_ogc.pth "
     "https://github.com/IDEA-Research/GroundingDINO/releases/download/v0.1.0/groundingdino_swint_ogc.pth"),

    ("安装 groundingdino 包", 
     "cd /root/autodl-tmp/streetview_analysis/groundingdino_repo && "
     "pip install -q -e . 2>&1 | tail -5"),

    ("安装补充依赖", 
     "pip install -q 'transformers>=4.9.0' 'accelerate>=0.20.0' 2>&1 | tail -3"),
]

for title, cmd in commands:
    print(f"\n=== {title} ===")
    stdin, stdout, stderr = c.exec_command(cmd, timeout=600)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    exit_code = stdout.channel.recv_exit_status()
    print(out.strip()[-500:] if out.strip() else "(无输出)")
    if err.strip(): print(f"[err] {err.strip()[-200:]}")
    print(f"[退出码: {exit_code}]")

# 上传检测脚本
print("\n=== 上传 grounding_dino_detect.py ===")
local_script = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\grounding_dino_detect.py"
sftp.put(local_script, f"{REMOTE_DIR}/groundingdino_detect.py")
print("上传完成")

sftp.close()
c.close()
print("\n=== 安装完成 ===")
