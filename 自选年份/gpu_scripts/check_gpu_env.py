#!/usr/bin/env python3
"""检查GPU字体环境，确认最优方案"""
import paramiko

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

# 1. 检查已安装的中文字体
print("=== 已安装的中文字体 ===")
out, err = run("fc-list :lang=zh 2>/dev/null | head -20")
print(out if out.strip() else "(无)")
out, err = run("find /usr/share/fonts /usr/local/share/fonts /root/.fonts -name '*.ttf' -o -name '*.ttc' 2>/dev/null | head -20")
print(out)

# 2. 检查字体文件位置
print("\n=== 常见字体位置 ===")
for d in ["/usr/share/fonts", "/usr/local/share/fonts", "/root/.fonts", "/home"]:
    out, err = run(f"ls {d} 2>/dev/null | head -5")
    if out.strip():
        print(f"{d}: {out.strip()[:100]}")

# 3. 检查 PIL
print("\n=== Python 环境 ===")
out, err = run("python3 -c \"from PIL import Image, ImageDraw, ImageFont; print('PIL OK'); import torch; print(f'PyTorch {torch.__version__}'); import ultralytics; print('Ultralytics OK')\" 2>&1")
print(out)

# 4. 检查 yolo11x.pt 位置
print("\n=== YOLO 模型 ===")
out, err = run("ls -lh /root/autodl-tmp/yolo11x.pt 2>/dev/null")
print(out)

# 5. GPU 显存
print("\n=== GPU ===")
out, err = run("nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null")
print(out)

# 6. 下载一个测试图片（确认速度）
print("\n=== 测试下载速度 ===")
sftp = ssh.open_sftp()
sftp.get("/root/autodl-tmp/streetview_images/Village/113.9263685_22.5129279/113.9263685_22.5129279_N_2022.jpg",
          "/tmp/test_speed.jpg")
sftp.close()
import os, time
t0 = time.time()
shutil_copy_test = None
print(f"单图测试完成: {os.path.getsize('/tmp/test_speed.jpg')/1024:.0f}KB")

# 7. 检查 /autodl-pub/data 是否可访问（更快的数据通道）
print("\n=== autodl-pub 公共数据 ===")
out, err = run("ls /autodl-pub/data/ 2>/dev/null | head -10")
print(out if out.strip() else "(不可访问)")

ssh.close()
print("\nDone")
