#!/usr/bin/env python3
"""用 heredoc 直接写脚本到远程并启动检测"""
import paramiko, time

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

# 杀掉旧进程
print("killing old...")
r(c, "kill -9 $(ps aux | grep -E 'detect|yolo_obstacle' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")
time.sleep(2)

# 读取本地脚本内容（base64编码避免所有编码问题）
import base64
script_path = r"e:\xicha gis 智能定位\自选年份\gpu_scripts\final_obstacle_detect.py"
with open(script_path, "r", encoding="utf-8") as f:
    script_content = f.read()

b64 = base64.b64encode(script_content.encode("utf-8")).decode("ascii")
print(f"Script size: {len(script_content)} chars, b64: {len(b64)} chars")

# 用 heredoc 写文件（远程用base64解码）
write_cmd = (
    f"cat > {REMOTE_DIR}/detect_final.py << 'HEREDOC_END'\n"
    + script_content
    + "\nHEREDOC_END"
)
print("Writing script to remote...")
out = r(c, write_cmd, timeout=60)
print(f"Write result: {out[:200] if out else 'OK (no output)'}")

# 验证
print("\n=== verify script written ===")
print(r(c, f"wc -l {REMOTE_DIR}/detect_final.py"))
print(r(c, f"head -3 {REMOTE_DIR}/detect_final.py"))
print(r(c, f"tail -3 {REMOTE_DIR}/detect_final.py"))

# 启动
print("\n=== starting detection ===")
r(c, f"cd {REMOTE_DIR} && python3 -u detect_final.py >> yolo_obstacle_run.log 2>&1 & echo PID=$!")
print("Started. Waiting 120s...")
time.sleep(120)

print("\n=== log after 120s ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== process ===")
print(r(c, "ps aux | grep detect_final | grep -v grep"))

print("\n=== processed images ===")
print(r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' 2>/dev/null | wc -l"))

c.close()
print("\nDONE")
