#!/usr/bin/env python3
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
        return "ERR:" + str(e)[:200]

print("=== 1. 检测进程状态 ===")
print(r(c, "ps aux | grep yolo_obstacle | grep -v grep"))

print("\n=== 2. 检测日志 ===")
print(r(c, "tail -30 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

print("\n=== 3. GPU状态 ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu,utilization.memory --format=csv,noheader"))

print("\n=== 4. 输出目录 ===")
print(r(c, "ls /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/ 2>/dev/null || echo 'no dir'"))

print("\n=== 5. JSON结果文件 ===")
print(r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results -name '*.json' 2>/dev/null"))

print("\n=== 6. 可视化图片数量 ===")
print(r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' 2>/dev/null | wc -l"))

print("\n=== 7. 图片总数 vs 已处理 ===")
total = r(c, "find /root/autodl-tmp/streetview_analysis/images -name '*.jpg' 2>/dev/null | wc -l")
processed = r(c, "find /root/autodl-tmp/streetview_analysis/yolo_obstacle_results/viz -name '*.jpg' 2>/dev/null | wc -l")
print(f"Total images: {total}")
print(f"Processed: {processed}")

print("\n=== 8. 最新日志 ===")
print(r(c, "tail -5 /root/autodl-tmp/streetview_analysis/yolo_obstacle_run.log"))

c.close()
