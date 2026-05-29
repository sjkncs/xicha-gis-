#!/usr/bin/env python3
"""全面检查 GPU 服务器数据"""
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

# 1. 全量街景图片数量
print("=== 全量街景图片 ===")
out, err = run('find /root/autodl-tmp/streetview_images/ -name "*.jpg" | wc -l')
print(f"街景图片总数: {out.strip()}")
out, err = run('find /root/autodl-tmp/streetview_images/ -name "*.jpg" | head -5')
print("示例路径:\n" + out)

# 2. 街景目录结构
print("\n=== 街景目录结构 ===")
out, err = run('find /root/autodl-tmp/streetview_images/ -maxdepth 2 -type d | sort')
print(out)

# 3. streetview_seg 结果
print("\n=== streetview_seg/results/ ===")
out, err = run('ls -la /root/autodl-tmp/streetview_seg/results/ | head -20')
print(out)
out, err = run('find /root/autodl-tmp/streetview_seg/results/ -name "*.png" | wc -l')
print(f"seg 标注图: {out.strip()}")

# 4. sim_results JSON 统计
print("\n=== sim_results.json ===")
out, err = run('cat /root/autodl-tmp/streetview_sim/sim_results.json | head -100')
print(out[:2000])

# 5. sim_results_v2.json
print("\n=== sim_results_v2.json ===")
out, err = run('cat /root/autodl-tmp/streetview_sim_v2/sim_results_v2.json | head -200')
print(out[:3000])

# 6. sim_v2.log 末尾（看运行状态）
print("\n=== sim_v2.log (最后30行) ===")
out, err = run('tail -30 /root/autodl-tmp/sim_v2.log')
print(out)

# 7. YOLO模型
print("\n=== YOLO 模型 ===")
out, err = run('ls -lh /root/autodl-tmp/yolo11x.pt')
print(out)

# 8. 磁盘剩余
print("\n=== 磁盘剩余 ===")
out, err = run('df -h /root/autodl-tmp/')
print(out)

ssh.close()
print("\nDone")
