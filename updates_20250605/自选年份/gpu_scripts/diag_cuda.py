#!/usr/bin/env python3
"""诊断CUDA环境 + yolo11x单张测试"""
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

# 杀掉所有旧进程
r(c, "kill -9 $(ps aux | grep 'diag_world\|yolo_obstacle\|test_yolo' | grep -v grep | awk '{print $2}') 2>/dev/null; echo killed")
time.sleep(2)

# 写测试脚本到远程（避免上传问题）
diag = [
    "#!/usr/bin/env python3",
    "import os, time, sys",
    "os.environ['YOLO_VERBOSE'] = 'False'",
    "print('START')",
    "import torch",
    "print('CUDA avail:', torch.cuda.is_available())",
    "print('GPU name:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')",
    "print('CUDA version:', torch.version.cuda)",
    "print('torch version:', torch.__version__)",
    "from ultralytics import YOLO",
    "MODEL = '/root/autodl-tmp/streetview_analysis/yolo_models/yolo11x.pt'",
    "print('Loading yolo11x...')",
    "t0 = time.time()",
    "m = YOLO(MODEL)",
    "print('YOLO loaded in', time.time()-t0, 's')",
    "m.to('cuda')",
    "print('to(cuda) OK')",
    "IMG = '/root/autodl-tmp/streetview_analysis/images'",
    "imgs = [os.path.join(r,f) for r,_,fs in os.walk(IMG) for f in fs if f.endswith('.jpg')]",
    "print('Found images:', len(imgs))",
    "if imgs:",
    "    print('Predicting on:', imgs[0])",
    "    t1 = time.time()",
    "    res = m.predict(imgs[0], conf=0.35, verbose=True)",
    "    print('DONE in', time.time()-t1, 's, boxes=', len(res[0].boxes))",
]

sftp = c.open_sftp()
sftp.file(f"{REMOTE_DIR}/diag_cuda.py", "wb").write("\n".join(diag).encode())
sftp.close()

r(c, f"cd {REMOTE_DIR} && python3 -u diag_cuda.py > diag_cuda.log 2>&1 & echo started PID=$!")
print("Waiting 90s for model load + 1 prediction...")
time.sleep(90)

print("=== diag log ===")
print(r(c, "cat /root/autodl-tmp/streetview_analysis/diag_cuda.log"))

print("\n=== GPU ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu,utilization.memory --format=csv,noheader"))

print("\n=== process ===")
print(r(c, "ps aux | grep diag_cuda | grep -v grep"))

c.close()
