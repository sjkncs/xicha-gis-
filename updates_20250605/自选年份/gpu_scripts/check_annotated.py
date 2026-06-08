#!/usr/bin/env python3
"""检查标注图和脚本，下载sim_results_v2.json"""
import paramiko, os

HOST = "connect.bjb1.seetacloud.com"
PORT = 18073
USER = "root"
PASS = "roBbKv+ed3Vm"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, banner_timeout=30)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    return stdout.read().decode("utf-8", errors="replace")

# 1. 检查 streetview_sim_v2/samples/
print("=== streetview_sim_v2/samples/ ===")
out = run("ls -la /root/autodl-tmp/streetview_sim_v2/samples/ 2>/dev/null || echo 'empty or no dir'")
print(out)

# 2. 检查所有标注图
print("\n=== 搜索所有标注图 ===")
out = run('find /root/autodl-tmp/ -name "*annotated*" -type f 2>/dev/null | head -20')
print(f"annotated 文件: {len(out.strip().split(chr(10)))} 个" if out.strip() else "无")
print(out)

# 3. 检查 sim_run_v2.py 脚本内容（确认字体设置）
print("\n=== sim_run_v2.py 字体设置 ===")
out = run("grep -n 'putText\\|font\\|Font\\|msyh\\|simhei\\|chinese\\|中文' /root/autodl-tmp/sim_run_v2.py 2>/dev/null | head -20")
print(out if out.strip() else "(未找到字体相关配置)")

# 4. 下载 sim_results_v2.json 到本地
print("\n=== 下载 sim_results_v2.json ===")
local_dir = r"e:\xicha gis 智能定位\自选年份\gpu_scripts"
os.makedirs(local_dir, exist_ok=True)
sftp = ssh.open_sftp()
sftp.get("/root/autodl-tmp/streetview_sim_v2/sim_results_v2.json",
          os.path.join(local_dir, "sim_results_v2.json"))
sftp.close()
print(f"[OK] 已下载到 {local_dir}\\sim_results_v2.json")

# 5. 下载 samples 目录内容（如果存在）
print("\n=== 下载 samples 目录 ===")
sftp = ssh.open_sftp()
try:
    files = sftp.listdir("/root/autodl-tmp/streetview_sim_v2/samples/")
    print(f"samples 目录有 {len(files)} 个文件")
    local_samples = os.path.join(local_dir, "samples_gpu")
    os.makedirs(local_samples, exist_ok=True)
    for fn in files:
        sftp.get(
            f"/root/autodl-tmp/streetview_sim_v2/samples/{fn}",
            os.path.join(local_samples, fn)
        )
    print(f"[OK] 下载到 {local_samples}")
except Exception as e:
    print(f"samples 下载失败: {e}")
sftp.close()

# 6. 检查脚本是否引用了正确的字体路径
print("\n=== sim_run_v2.py 字体相关行 ===")
out = run("grep -n 'FONT\\|ImageFont\\|truetype\\|Font' /root/autodl-tmp/sim_run_v2.py | head -20")
print(out)

ssh.close()
print("\nDone")
