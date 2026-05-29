#!/usr/bin/env python3
"""上传generate_json.py并执行"""
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

# 读取b64
with open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\generate_json.py", "r", encoding="utf-8") as f:
    script_content = f.read()
b64 = base64.b64encode(script_content.encode("utf-8")).decode("ascii")

# 上传
sftp = c.open_sftp()
sftp.file(f"{REMOTE_DIR}/generate_json.b64", "wb").write(b64.encode())
sftp.close()
print("b64 uploaded")

# 解码
out = r(c, f"base64 -d {REMOTE_DIR}/generate_json.b64 > {REMOTE_DIR}/generate_json.py && wc -l {REMOTE_DIR}/generate_json.py")
print(f"decode: {out}")

# 启动
print("starting JSON generation...")
r(c, f"cd {REMOTE_DIR} && python3 -u generate_json.py > gen_json.log 2>&1 & echo PID=$!")

# 等待（294张图预计3-5分钟）
time.sleep(180)

print("\n=== log ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/gen_json.log"))

print("\n=== JSON files ===")
print(r(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/*.json"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

c.close()
print("DONE")
