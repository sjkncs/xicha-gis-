#!/usr/bin/env python3
"""上传脚本到 GPU"""
import paramiko, os, sys

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"
SCRIPT = os.path.abspath(__file__).replace("\\", "/").replace(os.getcwd().replace("\\", "/"), "")
LOCAL_SCRIPT = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\gpu_full_render.py"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

sftp = ssh.open_sftp()

# 上传脚本
remote_path = "/root/autodl-tmp/gpu_full_render.py"
print(f"上传: {LOCAL_SCRIPT} -> {remote_path}")
sftp.put(LOCAL_SCRIPT, remote_path)

# 验证
st = sftp.stat(remote_path)
print(f"上传成功: {st.st_size} bytes")

# 先安装中文字体（下载 NotoSansSC）
cmds = [
    'mkdir -p /tmp/fonts',
    'apt-get install -y fonts-noto-cjk-extra 2>/dev/null || apt-get install -y fonts-noto-cjk 2>/dev/null || echo "apt install failed"',
    # 尝试 pip 安装字体（备用）
    'pip install fonttools 2>/dev/null; echo "fonttools ok"',
]

for cmd in cmds:
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if out.strip():
        print(f"  {cmd[:60]}: {out.strip()[:80]}")

# 验证字体
stdin, stdout, stderr = ssh.exec_command(
    "find /usr/share/fonts /root/.fonts /tmp/fonts -name '*noto*' -o -name '*cjk*' -o -name '*chinese*' 2>/dev/null | grep -i 'otf\\|ttf\\|ttc' | head -10",
    timeout=30)
out = stdout.read().decode("utf-8", errors="replace")
print(f"\n已安装字体:\n{out if out.strip() else '(无中文字体，将使用备用方案)'}\n")

# 尝试下载 NotoSansSC
print("下载 NotoSansSC 字体...")
cmd = '''curl -sL "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf" -o /tmp/NotoSansCJKsc.otf && ls -lh /tmp/NotoSansCJKsc.otf'''
stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
out = stdout.read().decode("utf-8", errors="replace")
err = stderr.read().decode("utf-8", errors="replace")
print(out if out.strip() else err)
if "NotoSansCJKsc.otf" in out or os.path.exists("/tmp/NotoSansCJKsc.otf"):
    pass

sftp.close()

print("脚本已上传，GPU环境已准备好")
print("下一步: 登录 GPU 运行: python /root/autodl-tmp/gpu_full_render.py")
