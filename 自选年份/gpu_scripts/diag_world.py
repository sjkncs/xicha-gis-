#!/usr/bin/env python3
"""诊断：逐个测试world模型每个阶段"""
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

# 1. world模型文件是否完整
print("=== 1. world模型文件 ===")
print(r(c, "ls -lh /root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-world.pt"))
print(r(c, "file /root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-world.pt"))

# 2. ultralytics版本
print("\n=== 2. ultralytics版本 ===")
print(r(c, "python3 -c \"import ultralytics; print(ultralytics.__version__)\""))

# 3. 逐阶段测试world模型
diag_script = r"""
#!/usr/bin/env python3
import os, time, sys
os.environ["YOLO_VERBOSE"] = "False"
print("START", flush=True)

print("Step1: import ultralytics...", flush=True)
from ultralytics import YOLO
print("Step1 OK", flush=True)

MODEL = "/root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-world.pt"
print(f"Step2: load model from {MODEL}...", flush=True)
t0 = time.time()
m = YOLO(MODEL)
print(f"Step2 OK in {time.time()-t0:.1f}s", flush=True)

print("Step3: set_classes...", flush=True)
m.set_classes(["person", "bicycle", "car", "traffic cone", "barrier"])
print("Step3 OK", flush=True)

print("Step4: to(cuda)...", flush=True)
m.to("cuda")
print("Step4 OK", flush=True)

IMG = "/root/autodl-tmp/streetview_analysis/images"
imgs = [os.path.join(r,f) for r,_,fs in os.walk(IMG) for f in fs if f.endswith('.jpg')]
if imgs:
    test_img = imgs[0]
    print(f"Step5: predict on {test_img}...", flush=True)
    t1 = time.time()
    r = m.predict(test_img, conf=0.35, verbose=False)
    print(f"Step5 OK in {time.time()-t1:.1f}s, boxes={len(r[0].boxes)}", flush=True)
else:
    print("No images found", flush=True)

print("ALL DONE", flush=True)
"""

import tempfile, os
tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
tmp.write(diag_script)
tmp.close()

sftp = c.open_sftp()
sftp.put(tmp.name, f"{REMOTE_DIR}/diag_world.py")
sftp.close()
os.unlink(tmp.name)
print(r(c, f"rm -f {REMOTE_DIR}/diag_world.py"))

# 直接在远程写文件内容（避免上传问题）
diag_lines = [
    "#!/usr/bin/env python3",
    "import os, time, sys",
    "os.environ['YOLO_VERBOSE'] = 'False'",
    "print('START')",
    "from ultralytics import YOLO",
    "MODEL = '/root/autodl-tmp/streetview_analysis/yolo_models/yolov8x-world.pt'",
    "print('Step2: loading...')",
    "m = YOLO(MODEL)",
    "print('Step2 OK, set_classes...')",
    "m.set_classes(['person','bicycle','car','traffic cone','barrier'])",
    "print('Step3 OK, to cuda...')",
    "m.to('cuda')",
    "print('Step4 OK')",
    "IMG = '/root/autodl-tmp/streetview_analysis/images'",
    "imgs = [os.path.join(r,f) for r,_,fs in os.walk(IMG) for f in fs if f.endswith('.jpg')]",
    "if imgs:",
    "    r = m.predict(imgs[0], conf=0.35, verbose=False)",
    "    print('Step5 OK, boxes=', len(r[0].boxes))",
    "print('ALL DONE')",
]
content = "\n".join(diag_lines)
sftp = c.open_sftp()
sftp.file(f"{REMOTE_DIR}/diag_world.py", "wb").write(content.encode())
sftp.close()

# 启动诊断脚本
print("\n=== 3. 启动world模型诊断 (60s超时) ===")
r(c, "kill -9 -f diag_world 2>/dev/null")
r(c, f"cd {REMOTE_DIR} && python3 -u diag_world.py > diag_world.log 2>&1 & echo started")
time.sleep(60)

print("\n=== 诊断日志 ===")
print(r(c, "cat /root/autodl-tmp/streetview_analysis/diag_world.log"))

print("\n=== GPU状态 ===")
print(r(c, "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader"))

print("\n=== 进程 ===")
print(r(c, "ps aux | grep diag_world | grep -v grep"))

c.close()
