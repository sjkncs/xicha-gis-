#!/usr/bin/env python3
"""安装依赖 + GPU分割模型完整基准测试"""
import paramiko, time

HOST = "connect.bjb1.seetacloud.com"; PORT = 12996
USER = "root"; PASS = "roBbKv+ed3Vm"
PYTHON_SYS = "/usr/bin/python3"
REMOTE_DIR = "/root/autodl-tmp"

def ssh():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30, allow_agent=False)
    return c

c = ssh()
sftp = c.open_sftp()

# 1. 安装依赖包
print("=== 安装依赖包 ===")
install_cmd = f"pip3 install transformers opencv-python-headless pillow scikit-image scipy pandas scikit-learn albumentations matplotlib --index-url https://download.pytorch.org/whl/cu124 -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 600 >> {REMOTE_DIR}/deps.log 2>&1 &"
c.exec_command(install_cmd, timeout=10)
print("依赖安装已后台启动")

time.sleep(5)
stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip3 install' | grep -v grep | head -2", timeout=10)
print(stdout.read().decode().strip()[:200])

# 2. 分割模型GPU基准测试
print("\n=== GPU分割模型基准测试 ===")
seg_bench = r"""#!/usr/bin/python3
import torch, time, sys

LOG = "/root/autodl-tmp/seg_bench_result.txt"
def log(msg):
    with open(LOG, "a") as f: f.write(msg + "\n")
    print(msg, flush=True)

log("TORCH=" + torch.__version__)
log("CUDA=" + str(torch.version.cuda))
log("GPU=" + torch.cuda.get_device_name(0))

# 预热
torch.cuda.empty_cache()

# 1. FCN_ResNet50 单图
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    m = fcn_resnet50(weights="DEFAULT").cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 100 / (time.time() - t0)
    log("FCN_SINGLE_512_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("FCN_SINGLE_FAIL=" + str(e)[:150])

# 2. FCN 批处理8张
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    m = fcn_resnet50(weights="DEFAULT").cuda()
    m.eval()
    x = torch.randn(8, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 400 / (time.time() - t0)
    log("FCN_BATCH8_512_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("FCN_BATCH8_FAIL=" + str(e)[:150])

# 3. DeepLabV3 单图
try:
    from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
    m = deeplabv3_resnet50(weights="DEFAULT").cuda()
    m.eval()
    x = torch.randn(1, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 100 / (time.time() - t0)
    log("DEEPLABV3_SINGLE_512_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("DEEPLABV3_SINGLE_FAIL=" + str(e)[:150])

# 4. DeepLabV3 批处理8张
try:
    from torchvision.models.segmentation.deeplabv3 import deeplabv3_resnet50
    m = deeplabv3_resnet50(weights="DEFAULT").cuda()
    m.eval()
    x = torch.randn(8, 3, 512, 512).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(50): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 400 / (time.time() - t0)
    log("DEEPLABV3_BATCH8_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("DEEPLABV3_BATCH8_FAIL=" + str(e)[:150])

# 5. CPU基准对比 (LRASPP轻量)
try:
    from torchvision.models.segmentation.lrasnet import lrasnet_lowresnet34, lrasnet_mobilenet3_small
    m = lrasnet_mobilenet3_small(weights="DEFAULT")
    m.eval()
    x = torch.randn(1, 3, 512, 512)
    with torch.no_grad():
        for _ in range(3): r = m(x)['out']
    t0 = time.time()
    with torch.no_grad():
        for _ in range(20): r = m(x)['out']
    fps = 20 / (time.time() - t0)
    log("LRASPP_SMALL_CPU_FPS=" + str(round(fps, 1)))
    del m
except Exception as e:
    log("LRASPP_CPU_FAIL=" + str(e)[:150])

# 6. GPU下采样分割 (256px更快)
try:
    from torchvision.models.segmentation.fcn import fcn_resnet50
    m = fcn_resnet50(weights="DEFAULT").cuda()
    m.eval()
    x = torch.randn(8, 3, 256, 256).cuda()
    with torch.no_grad():
        for _ in range(5): r = m(x)['out']
    torch.cuda.synchronize()
    t0 = time.time()
    with torch.no_grad():
        for _ in range(100): r = m(x)['out']
    torch.cuda.synchronize()
    fps = 800 / (time.time() - t0)
    log("FCN_BATCH8_256_FPS=" + str(round(fps, 1)))
    del m; torch.cuda.empty_cache()
except Exception as e:
    log("FCN_256_FAIL=" + str(e)[:150])

# 7. 图像处理测试
try:
    import cv2, numpy as np
    img = np.random.randint(0, 255, (512, 512, 3), dtype=np.uint8)
    t0 = time.time()
    for _ in range(1000):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
    fps = 1000 / (time.time() - t0)
    log("CV2_PREPROCESS_FPS=" + str(round(fps, 1)))
except Exception as e:
    log("CV2_FAIL=" + str(e)[:100])

log("BENCHMARK_DONE")
"""

with sftp.open(REMOTE_DIR + "/seg_bench.py", "w") as f:
    f.write(seg_bench)

channel = c.get_transport().open_session()
channel.exec_command(PYTHON_SYS + " " + REMOTE_DIR + "/seg_bench.py 2>&1")

print("分割模型基准测试运行中（预计2-3分钟）...")
time.sleep(120)

try:
    with sftp.open(REMOTE_DIR + "/seg_bench_result.txt") as f:
        print("\n=== 基准测试结果 ===")
        for line in f.read().decode().strip().split('\n'):
            if line.strip():
                print(f"  {line}")
except FileNotFoundError:
    print("结果还没出来，再等30s...")
    time.sleep(30)
    try:
        with sftp.open(REMOTE_DIR + "/seg_bench_result.txt") as f:
            for line in f.read().decode().strip().split('\n'):
                if line.strip():
                    print(f"  {line}")
    except:
        print("仍未完成")

# 检查依赖安装
print("\n=== 依赖安装状态 ===")
stdin, stdout, stderr = c.exec_command("ps aux | grep 'pip3 install' | grep -v grep | head -2", timeout=10)
print(stdout.read().decode().strip()[:200])

stdin, stdout, stderr = c.exec_command("tail -3 " + REMOTE_DIR + "/deps.log 2>/dev/null", timeout=10)
print(stdout.read().decode().strip()[:200])

sftp.close()
c.close()
print("\n完成!")
