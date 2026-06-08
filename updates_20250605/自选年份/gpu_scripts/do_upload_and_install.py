#!/usr/bin/env python3
"""上传脚本到 GPU 并启动"""
import paramiko, os

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"
LOCAL_SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\gpu_full_render.py"
REMOTE_SCRIPT = "/root/autodl-tmp/gpu_full_render.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
sftp = ssh.open_sftp()

print(f"上传: {LOCAL_SCRIPT}")
sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
st = sftp.stat(REMOTE_SCRIPT)
print(f"上传成功: {st.st_size} bytes")
sftp.close()

# 安装字体
cmds_font = [
    ("下载中文字体", 'curl -sL "https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/07_NotoSansCJKsc-Regular.otf" -o /tmp/NotoSansCJK.otf 2>&1 || wget -q "https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/07_NotoSansCJKsc-Regular.otf" -O /tmp/NotoSansCJK.otf 2>&1'),
    ("验证字体", "ls -lh /tmp/NotoSansCJK.otf 2>/dev/null || echo 'font not found'"),
]
for name, cmd in cmds_font:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    print(f"  [{name}]: {out.strip() or err.strip()[:80]}")

# 清理旧结果（如果有）
stdin, stdout, stderr = ssh.exec_command("mkdir -p /root/autodl-tmp/streetview_sim_full/results /root/autodl-tmp/streetview_sim_full/raw; ls /root/autodl-tmp/streetview_sim_full/results/ | wc -l", timeout=30)
print(f"  [目录]: {stdout.read().decode().strip()}")

ssh.close()
print("\n=== 准备完成 ===")
print("请在 GPU 终端运行以下命令（建议用 nohup 后台运行）：")
print(f"  cd /root/autodl-tmp && python gpu_full_render.py")
print("\n或运行以下命令立即启动（自动后台）：")
print(f"  nohup python /root/autodl-tmp/gpu_full_render.py > /root/autodl-tmp/full_render.log 2>&1 &")
print(f"  echo $! > /root/autodl-tmp/full_render.pid")
