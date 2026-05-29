#!/usr/bin/env python3
"""sftp上传 + 远程解码 + 启动"""
import paramiko, time, base64

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
REMOTE_DIR = "/root/autodl-tmp/streetview_analysis"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)
c.get_transport().set_keepalive(30)

def r(c, cmd, timeout=30):
    try:
        stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
        return stdout.read().decode("utf-8", errors="replace").strip()
    except Exception as e:
        return "ERR:" + str(e)[:100]

# 1. 杀掉旧进程
print("killing old...")
r(c, "kill -9 $(ps aux | grep -E 'detect|yolo_obstacle' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")

# 2. 读取b64内容
with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\script_b64.txt", "r") as f:
    b64_content = f.read().strip()
print(f"b64 content length: {len(b64_content)}")

# 3. sftp上传b64文件
sftp = c.open_sftp()
sftp.file(f"{REMOTE_DIR}/detect_script.b64", "wb").write(b64_content.encode())
sftp.close()
print("b64 file uploaded")

# 4. 远程解码并写脚本
print("decoding on remote...")
decode_cmd = (
    f"base64 -d {REMOTE_DIR}/detect_script.b64 > {REMOTE_DIR}/detect_final.py "
    f"&& echo OK && wc -l {REMOTE_DIR}/detect_final.py"
)
out = r(c, decode_cmd, timeout=60)
print(f"decode: {out}")

# 5. 验证脚本
print(f"head: {r(c, f'head -3 {REMOTE_DIR}/detect_final.py')}")
print(f"tail: {r(c, f'tail -3 {REMOTE_DIR}/detect_final.py')}")

# 6. 启动检测
print("starting...")
r(c, f"cd {REMOTE_DIR} && python3 -u detect_final.py >> yolo_obstacle_run.log 2>&1 & echo PID=$!")
print("Started. Waiting 120s...")
time.sleep(120)

# 7. 检查
print("\n=== log ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process ===")
print(r(c, "ps aux | grep detect_final | grep -v grep"))

print("\n=== processed images ===")
print(r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' 2>/dev/null | wc -l"))

c.close()
print("DONE")
