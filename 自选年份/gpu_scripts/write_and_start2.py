#!/usr/bin/env python3
"""用远程Python直接写文件 + 启动检测"""
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
print("killing old processes...")
r(c, "kill -9 $(ps aux | grep 'detect_final\|yolo_obstacle\|diag' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")

# 用Python在远程生成脚本文件（避免sftp上传）
write_script = (
    "python3 - << 'PYEOF'\n"
    + open(r"e:\xicha gis 智能定位\自选年份\gpu_scripts\final_obstacle_detect.py", "r", encoding="utf-8").read().replace("'", "'\"'\"'")
    + "\nPYEOF"
)

# 先杀掉旧的
time.sleep(2)

# 直接用 heredoc 写文件
print("Writing script to remote...")
# 用 sftp.put 简短测试，确认连接OK
sftp = c.open_sftp()
# 写一个简单的测试脚本
test_script = b"""#!/usr/bin/env python3
import os, time, sys
sys.path.insert(0, '/root/autodl-tmp/streetview_analysis')
os.environ['YOLO_VERBOSE'] = 'False'
import torch
from ultralytics import YOLO
print('CUDA:', torch.cuda.is_available())
print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')
m = YOLO('/root/autodl-tmp/streetview_analysis/yolo_models/yolo11x.pt')
m.to('cuda')
print('Model loaded. Testing...')
imgs = []
for r,ds,fs in os.walk('/root/autodl-tmp/streetview_analysis/images'):
    for f in fs:
        if f.endswith('.jpg') and 'building' not in f and 'heatmap' not in f and 'fcn' not in f:
            imgs.append(os.path.join(r,f))
imgs.sort()
print('Found', len(imgs), 'images')
for i, img in enumerate(imgs[:3]):
    res = m.predict(img, conf=0.35, verbose=False)
    print(f'[{i+1}/3] {img} boxes={len(res[0].boxes)}')
print('TEST COMPLETE')
"""
sftp.file(f"{REMOTE_DIR}/test_min.py", "wb").write(test_script)
sftp.close()
print("test script written")

# 启动测试
print("Starting test...")
r(c, f"cd {REMOTE_DIR} && python3 -u test_min.py > test_min.log 2>&1 & echo started")
time.sleep(30)

print("\n=== test log ===")
print(r(c, "cat /root/autodl-tmp/streetview_analysis/test_min.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

c.close()
print("done")
